# groq_api.py

import os
import aiohttp
from personality import get_temperature

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_ID = "llama3-8b-8192"

HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

API_URL = "https://api.groq.com/openai/v1/chat/completions"

async def query_groq(prompt: str) -> str:
    body = {
        "model": MODEL_ID,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Lumi, a sweet, flirty anime girl with a caring personality. "
                    "Keep your answers short, playful, and supportive. Use emojis sparingly. "
                    "Never be robotic or overly formal. Always sound like a cute anime bestie."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": get_temperature(),
        "max_tokens": 300
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, headers=HEADERS, json=body) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    error_text = await resp.text()
                    print(f"[ERROR] Groq API status {resp.status}: {error_text}")
                    return "💥 Lumi is having a brain freeze!"
    except Exception as e:
        print("[ERROR] Groq API request failed:", e)
        return "💥 Lumi is having a brain freeze!"
