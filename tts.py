import os
import requests
from dotenv import load_dotenv

load_dotenv()

ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")
VOICE_ID = os.getenv("ELEVEN_VOICE_ID")

def text_to_speech(text):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"

    headers = {
        "xi-api-key": ELEVEN_API_KEY,
        "Content-Type": "application/json"
    }

    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }

    try:
        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            audio_path = "milla_voice.mp3"
            with open(audio_path, "wb") as f:
                f.write(response.content)
            print("[DEBUG] Voice saved as milla_voice.mp3")

            # Jalankan mpg123 dari path absolut
            player_path = "Z:\\MillaWebBot\\mpg123.exe"
            os.system(f'"{player_path}" {audio_path}')

        else:
            print(f"[ERROR] ElevenLabs API Error: {response.status_code}")
            print(response.text)

    except Exception as e:
        print(f"[ERROR] TTS Error: {e}")