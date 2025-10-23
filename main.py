import os
import threading
import mimetypes
import time
from datetime import datetime
from flask import Flask, render_template, request, send_file, jsonify
import yt_dlp
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2
import requests
import pytz

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

progress = 0
downloading = False
current_file = None
current_title = None
current_format = None
current_duration = None
current_size = None
file_lock = threading.Lock()

log_file = "download_log.txt"
MAX_LOGS = 50
MAX_DURATION_SECONDS = 3 * 60 * 60  # 3 jam = 10800 detik

def format_size(bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024
    return f"{bytes:.1f} TB"

def format_duration(seconds):
    if not seconds:
        return "0:00"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fetch-info', methods=['POST'])
def fetch_info():
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL kosong'}), 400
    try:
        with yt_dlp.YoutubeDL({
            'quiet': True,
            'cookiefile': 'cookies.txt'
        }) as ydl:
            info = ydl.extract_info(url, download=False)
            duration = info.get("duration", 0)
            if duration > MAX_DURATION_SECONDS:
                return jsonify({'error': 'Durasi video lebih dari 3 jam tidak didukung.'}), 400
            return jsonify({
                'title': info.get('title'),
                'thumbnail': info.get('thumbnail'),
                'duration': duration
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/progress')
def get_progress():
    return jsonify({'progress': progress, 'downloading': downloading})

def update_progress_hook(d):
    global progress
    if d.get('status') == 'downloading':
        downloaded = d.get('downloaded_bytes', 0)
        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 1
        progress = int(downloaded / total * 100)

def embed_thumbnail(mp3_path, thumb_url, title):
    audio = MP3(mp3_path, ID3=ID3)
    try:
        audio.add_tags()
    except:
        pass
    image_data = requests.get(thumb_url).content
    audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=image_data))
    audio.tags.add(TIT2(encoding=3, text=title))
    audio.save()

def sanitize_filename(name):
    return "".join(c for c in name if c.isalnum() or c in " _-").rstrip()

def log_download(title, fmt, duration, size):
    wib = pytz.timezone("Asia/Jakarta")
    timestamp = datetime.now(wib).strftime('%d/%m/%Y - %H:%M')
    entry = f"{timestamp} | {fmt.upper()} | {duration} | {size} | {title}\n"

    if os.path.exists(log_file) and os.path.isfile(log_file):
        with open(log_file, 'r') as f:
            lines = f.readlines()
    else:
        lines = []

    lines.append(entry)
    if len(lines) > MAX_LOGS:
        lines = lines[-MAX_LOGS:]

    with open(log_file, 'w') as f:
        f.writelines(lines)

def download_thread(url, fmt):
    global progress, downloading, current_file, current_title, current_format, current_duration, current_size
    downloading = True
    progress = 0
    with file_lock:
        current_file = None
        current_title = None
        current_format = fmt
        current_duration = None
        current_size = None

    opts = {
        'quiet': True,
        'progress_hooks': [update_progress_hook],
        'outtmpl': 'temp.%(ext)s',
        'cookiefile': 'cookies.txt'
    }

    if fmt == 'mp3':
        opts.update({
            'format': 'bestaudio[ext=m4a]/bestaudio',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '64'
            }]
        })
    else:
        opts.update({
            'format': 'bestvideo[height<=360]+bestaudio/best[height<=360]',
            'merge_output_format': 'mp4',
        })

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            duration_secs = info.get('duration', 0)
            title = sanitize_filename(info.get('title', 'video'))
            duration = format_duration(duration_secs)
            thumb = info.get('thumbnail')
            file_path = ydl.prepare_filename(info)
            base, ext = os.path.splitext(file_path)

            if fmt == 'mp3':
                filename = base + '.mp3'
            else:
                filename = base + '.mp4'
                if not os.path.exists(filename):
                    for f in os.listdir('.'):
                        if f.startswith('temp') and f.endswith('.mp4'):
                            filename = f
                            break

            if fmt == 'mp3' and os.path.exists(filename):
                embed_thumbnail(filename, thumb, title)

            final_name = f"{title}.{fmt}"
            dest_path = os.path.join("downloads", final_name)

            if os.path.exists(dest_path):
                os.remove(dest_path)
            os.rename(filename, dest_path)

            size = format_size(os.path.getsize(dest_path))

            with file_lock:
                current_file = dest_path
                current_title = title
                current_format = fmt
                current_duration = duration
                current_size = size

            print(f"[SERVER] File siap: {dest_path}")
    except Exception as e:
        print("Error:", e)

    progress = 100
    downloading = False

def delayed_cleanup(seconds=5):
    def cleanup():
        time.sleep(seconds)
        for f in os.listdir("downloads"):
            try:
                os.remove(os.path.join("downloads", f))
                print(f"[CLEANUP] Hapus: {f}")
            except Exception as e:
                print(f"[CLEANUP] Gagal hapus {f}: {e}")
    threading.Thread(target=cleanup).start()

@app.route('/download', methods=['POST'])
def start_download():
    global downloading
    if downloading:
        return jsonify({'error': 'Sedang mendownload file'}), 400
    data = request.get_json()
    url = data.get('url')
    fmt = data.get('format')
    if not url or fmt not in ['mp3', 'mp4']:
        return jsonify({'error': 'Data tidak valid'}), 400
    thread = threading.Thread(target=download_thread, args=(url, fmt))
    thread.start()
    return jsonify({'status': 'started'})

@app.route('/file', methods=['GET'])
def get_file():
    max_wait = 10
    interval = 0.5
    waited = 0

    while waited < max_wait:
        with file_lock:
            path = current_file
            title = current_title
            fmt = current_format
            duration = current_duration
            size = current_size
        if path and os.path.exists(path):
            mime_type, _ = mimetypes.guess_type(path)
            filename = os.path.basename(path)
            print(f"[SERVER] Mengirim file ke browser: {filename}")

            log_download(title, fmt, duration, size)
            delayed_cleanup(5)

            return send_file(path, mimetype=mime_type, as_attachment=True, download_name=filename)
        time.sleep(interval)
        waited += interval

    print("[SERVER] Gagal menemukan file untuk dikirim.")
    return jsonify({'error': 'File tidak ditemukan'}), 404

if __name__ == '__main__':
    os.makedirs("downloads", exist_ok=True)
    app.run(host='0.0.0.0', port=81)