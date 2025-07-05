from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import os
import requests
import json
from tts import text_to_speech

# Load environment variables
load_dotenv()

app = Flask(__name__)
api_key = os.getenv("OPENROUTER_API_KEY")

print(f"[DEBUG] API Key Loaded: {api_key[:10]}...")

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get("message")
    print(f"[DEBUG] User Message: {user_msg}")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "Milla Moochille WaifuBot"
    }

    system_prompt = "Kamu adalah Milla Moochille, waifu AI sapi yang menggoda, lembut, dewasa, dan imut. Selalu balas dengan gaya manja dan sedikit genit, namun tetap sopan."

    def generate_payload(model_name):
        return {
            "model": model_name,
            "max_tokens": 300,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg}
            ]
        }

    def try_model(model_name):
        data = generate_payload(model_name)
        print(f"[DEBUG] Using model: {model_name}")
        print(f"[DEBUG] Payload Data: {json.dumps(data, indent=2)}")
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        print(f"[DEBUG] Response Status Code: {response.status_code}")
        print(f"[DEBUG] Response Text: {response.text}")
        return response

    try:
        response = try_model("openai/gpt-4o")

        if response.status_code == 402 or "error" in response.text:
            print("[INFO] Gagal pakai GPT-4o, mencoba fallback ke GPT-3.5-turbo...")
            response = try_model("openai/gpt-3.5-turbo")

        result = response.json()
        reply = result["choices"][0]["message"]["content"]

        # 🗣️ Konversi teks ke suara
        text_to_speech(reply)

    except Exception as e:
        print(f"[ERROR] Exception occurred: {e}")
        reply = "Moo~ Milla tidak menerima jawaban dari server 😢"

    return jsonify({"reply": reply})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)