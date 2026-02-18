import os
import aiohttp
from personality import get_temperature, get_system_prompt

MODEL_ID = "llama-3.3-70b-versatile"
API_URL = "https://api.groq.com/openai/v1/chat/completions"

# ✅ ADD 'server_emojis' to the arguments here
async def query_groq(prompt: str, server_emojis: str = "") -> str:
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
                # ✅ Pass the server_emojis into your personality prompt
                "content": get_system_prompt(server_emojis)
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
            async with session.post(API_URL, headers=headers, json=body) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    message = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    return message if message else "💬 Hmm... I didn’t quite catch that."
                else:
                    error_text = await resp.text()
                    print(f"[ERROR] Groq API status {resp.status}: {error_text}")
                    return "⚠️ My brain is a bit fuzzy right now..."
    except Exception as e:
        print("[ERROR] Groq API request failed:", e)
        return "💥 Lumi crashed into a wall of code!"
