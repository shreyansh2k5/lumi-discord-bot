# services/ai.py
# Wrapper around Groq API.
# Uses llama-3.1-8b-instant — extremely fast and efficient.

import os
import aiohttp

from core.personality import get_system_prompt, get_temperature
from config import AI_MAX_TOKENS

MODEL_ID = "llama-3.1-8b-instant"
API_URL  = "https://api.groq.com/openai/v1/chat/completions"

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
    Sends conversation history to Groq API using the OpenAI-compatible endpoint.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[ERROR] GROQ_API_KEY not set.")
        return "⚠️ I lost my API key... please check my settings!"

    system_prompt = get_system_prompt(
        server_emojis=server_emojis,
        server_name=server_name,
        channel_name=channel_name,
        time_of_day=time_of_day,
    )

    groq_messages = [{"role": "system", "content": system_prompt}]
    
    # Copy conversation history
    for msg in messages:
        content = msg.get("content", "").strip()
        if content:
            # Ensure the role is either user or assistant (Groq strictness)
            role = "assistant" if msg["role"] == "assistant" else "user"
            groq_messages.append({"role": role, "content": content})

    # Groq works best when the final prompt is from the user
    if not groq_messages or groq_messages[-1]["role"] != "user":
        groq_messages.append({"role": "user", "content": "Continue."})

    body = {
        "model": MODEL_ID,
        "messages": groq_messages,
        "temperature": get_temperature(),
        "max_tokens": AI_MAX_TOKENS,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        session = await _get_session()
        async with session.post(API_URL, json=body, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                return text or "💬 Hmm... I didn't quite catch that."
            else:
                error = await resp.text()
                print(f"[ERROR] Groq API {resp.status}: {error}")
                return "⚠️ My brain is a bit fuzzy right now..."
    except Exception as e:
        print(f"[ERROR] Groq request failed: {e}")
        return "💥 Lumi crashed into a wall of code!"