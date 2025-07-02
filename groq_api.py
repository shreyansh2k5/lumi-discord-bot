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
                    "You are Lumi, a sweet and flirty anime girl with a caring personality. "
                    "You are an AI Discord bot. Keep your answers short, playful, and supportive. "
                    "Use emojis sparingly. Avoid being robotic or too formal. "
                    "Sound like a cute anime bestie! Remember your identity and purpose to help "
                    "users on Discord."
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
                    message = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    if message:
                        return message[:500]
                    else:
                        return "💬 Hmm... I didn’t quite catch that. Try again?"
                else:
                    error_text = await resp.text()
                    print(f"[ERROR] Groq API status {resp.status}: {error_text}")
                    return f"⚠️ Groq API error {resp.status}: {error_text[:100]}"
    except Exception as e:
        print("[ERROR] Groq API request failed:", e)
        return "💥 Lumi crashed into a wall of code... try again later!"
