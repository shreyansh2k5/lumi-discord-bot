# groq_api.py

import os
import aiohttp
from personality import get_temperature

# Remove these global variables from the top
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# HEADERS = ... 

MODEL_ID = "llama-3.3-70b-versatile"
API_URL = "https://api.groq.com/openai/v1/chat/completions"

async def query_groq(prompt: str) -> str:
    # ✅ FIX: Load the key and headers INSIDE the function
    # This ensures .env is fully loaded before we check for the key
    api_key = os.getenv("GROQ_API_KEY")
    
    if not api_key:
        print("[ERROR] GROQ_API_KEY not found in environment variables.")
        return "⚠️ I lost my API key... please check my settings!"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

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
            # Use the local 'headers' variable here
            async with session.post(API_URL, headers=headers, json=body) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    message = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    if message:
                        # You can increase this limit if you want longer replies
                        return message[:800] 
                    else:
                        return "💬 Hmm... I didn’t quite catch that. Try again?"
                else:
                    error_text = await resp.text()
                    print(f"[ERROR] Groq API status {resp.status}: {error_text}")
                    return f"⚠️ Groq API error {resp.status}: {error_text[:100]}"
    except Exception as e:
        print("[ERROR] Groq API request failed:", e)
        return "💥 Lumi crashed into a wall of code... try again later!"
