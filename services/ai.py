# services/ai.py
# Wrapper around the Groq API. Reuses a single aiohttp session for efficiency.

import os
import aiohttp

from core.personality import get_system_prompt, get_temperature
from config import AI_MAX_TOKENS

MODEL_ID = "llama-3.3-70b-versatile"
API_URL  = "https://api.groq.com/openai/v1/chat/completions"

# Single session reused across all requests (created on first call)
_session: aiohttp.ClientSession | None = None


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session


async def query_groq(prompt: str, server_emojis: str = "") -> str:
    """
    Sends a prompt to the Groq API and returns Lumi's response.
    Uses a persistent aiohttp session instead of creating a new one per call.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[ERROR] GROQ_API_KEY not set.")
        return "⚠️ I lost my API key... please check my settings!"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": get_system_prompt(server_emojis)},
            {"role": "user",   "content": prompt},
        ],
        "temperature": get_temperature(),
        "max_tokens": AI_MAX_TOKENS,
    }

    try:
        session = await _get_session()
        async with session.post(API_URL, headers=headers, json=body) as resp:
            if resp.status == 200:
                data = await resp.json()
                text = (
                    data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                        .strip()
                )
                return text or "💬 Hmm... I didn't quite catch that."
            else:
                error = await resp.text()
                print(f"[ERROR] Groq API {resp.status}: {error}")
                return "⚠️ My brain is a bit fuzzy right now..."
    except Exception as e:
        print(f"[ERROR] Groq request failed: {e}")
        return "💥 Lumi crashed into a wall of code!"
