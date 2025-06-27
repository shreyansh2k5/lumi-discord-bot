# groq_api.py

import os
import requests
from personality import get_temperature
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_ID = "llama3-8b-8192"

def query_groq(prompt: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": "You are Lumi, a flirty and playful anime girl who is caring and witty. Keep replies short, cute, and in-character."},
            {"role": "user", "content": prompt}
        ],
        "temperature": get_temperature(),
        "max_tokens": 200
    }

    try:
        res = requests.post(url, headers=headers, json=data)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("[ERROR] Groq API:", e)
        return "💥 Lumi is having a brain freeze!"
