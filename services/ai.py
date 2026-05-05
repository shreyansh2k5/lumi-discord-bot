# services/ai.py
# OpenRouter API wrapper (Owl model)

import os
import aiohttp

from core.personality import get_system_prompt, get_temperature
from config import AI_MAX_TOKENS

MODEL_ID = "openrouter/owl-alpha"
API_URL  = "https://openrouter.ai/api/v1/chat/completions"

_session: aiohttp.ClientSession | None = None


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session


async def query_ai(
    messages: list[dict],
    server_emojis: str = "",
    server_name: str = "",
    channel_name: str = "",
    time_of_day: str = "",
) -> str:
    """
    Sends conversation history to OpenRouter (Owl model).
    """

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("[ERROR] OPENROUTER_API_KEY not set.")
        return "⚠️ I lost my API key... please check my settings!"

    system_prompt = get_system_prompt(
        server_emojis=server_emojis,
        server_name=server_name,
        channel_name=channel_name,
        time_of_day=time_of_day,
    )

    # Build message list
    ai_messages = [{"role": "system", "content": system_prompt}]

    for msg in messages:
        content = msg.get("content", "").strip()
        if content:
            role = "assistant" if msg["role"] == "assistant" else "user"
            ai_messages.append({"role": role, "content": content})

    # Ensure last message is user (important for OpenRouter too)
    if not ai_messages or ai_messages[-1]["role"] != "user":
        ai_messages.append({"role": "user", "content": "Continue."})

    body = {
        "model": MODEL_ID,
        "messages": ai_messages,
        "temperature": get_temperature(),
        "max_tokens": AI_MAX_TOKENS,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://lumi-bot.app",  # can be anything
        "X-Title": "Lumi Discord Bot"
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
                print(f"[ERROR] OpenRouter {resp.status}: {error}")
                return "⚠️ My brain is a bit fuzzy right now..."
    except Exception as e:
        print(f"[ERROR] OpenRouter request failed: {e}")
        return "💥 Lumi crashed into a wall of code!"