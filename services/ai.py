# services/ai.py
# Wrapper around Google Gemini API (free tier).
# Uses gemini-1.5-flash — fast, free, 1M token context window.

import os
import aiohttp

from core.personality import get_system_prompt, get_temperature
from config import AI_MAX_TOKENS

MODEL_ID = "gemini-2.5-flash"
API_URL  = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

_session: aiohttp.ClientSession | None = None


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session


async def query_groq(
    messages: list[dict],
    server_emojis: str = "",
    server_name: str = "",
    channel_name: str = "",
    time_of_day: str = "",
) -> str:
    """
    Sends conversation history to Gemini API.
    Function kept as query_groq so no other files need changing.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY not set.")
        return "⚠️ I lost my API key... please check my settings!"

    system_prompt = get_system_prompt(
        server_emojis=server_emojis,
        server_name=server_name,
        channel_name=channel_name,
        time_of_day=time_of_day,
    )

    # Convert OpenAI-style messages to Gemini format
    # Gemini uses "user"/"model" roles and "parts" instead of "content"
    gemini_contents = []
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        gemini_contents.append({
            "role": role,
            "parts": [{"text": msg["content"]}]
        })

    # If last message isn't from user, Gemini errors — ensure it ends with user
    if not gemini_contents or gemini_contents[-1]["role"] != "user":
        gemini_contents.append({"role": "user", "parts": [{"text": "Continue."}]})

    body = {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": gemini_contents,
        "generationConfig": {
            "temperature":    get_temperature(),
            "maxOutputTokens": AI_MAX_TOKENS,
        },
    }

    url = API_URL.format(model=MODEL_ID, key=api_key)

    try:
        session = await _get_session()
        async with session.post(url, json=body) as resp:
            if resp.status == 200:
                data = await resp.json()
                text = (
                    data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")
                        .strip()
                )
                return text or "💬 Hmm... I didn't quite catch that."
            else:
                error = await resp.text()
                print(f"[ERROR] Gemini API {resp.status}: {error}")
                return "⚠️ My brain is a bit fuzzy right now..."
    except Exception as e:
        print(f"[ERROR] Gemini request failed: {e}")
        return "💥 Lumi crashed into a wall of code!"