# services/ai.py
# OpenRouter API wrapper (Nemotron model)

import os

import aiohttp

from config import AI_MAX_TOKENS
from core.personality import get_system_prompt, get_temperature

MODEL_ID = "nvidia/nemotron-3.5-super-vl:free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

_session: aiohttp.ClientSession | None = None


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session


async def query_model(
    messages: list[dict],
    server_emojis: str = "",
    server_name: str = "",
    channel_name: str = "",
    time_of_day: str = "",
) -> str:
    """Send conversation history to OpenRouter using Nemotron."""
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

    ai_messages = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        content = msg.get("content", "").strip()
        if content:
            role = "assistant" if msg["role"] == "assistant" else "user"
            ai_messages.append({"role": role, "content": content})

    if ai_messages[-1]["role"] != "user":
        ai_messages.append({"role": "user", "content": "Continue."})

    body = {
        "model": MODEL_ID,
        "messages": ai_messages,
        "temperature": get_temperature(),
        "max_tokens": AI_MAX_TOKENS,
        "reasoning": {"enabled": False},
    }
    headers = {
        "Content-Type": "application/json",
        "HTTP-Referer": "https://lumi-bot.app",
        "X-Title": "Lumi Discord Bot",
    }
    headers["Authorization"] = "Bearer " + api_key

    try:
        session = await _get_session()
        async with session.post(API_URL, json=body, headers=headers) as resp:
            data = await resp.json(content_type=None)
            if resp.status == 200:
                message = data.get("choices", [{}])[0].get("message", {})
                text = (message.get("content") or "").strip()
                if text:
                    return text
                print(f"[ERROR] OpenRouter returned no message text: {data}")
                return "⚠️ I received an empty response from my AI service."

            print(f"[ERROR] OpenRouter {resp.status}: {data}")
            return "⚠️ My brain is a bit fuzzy right now..."
    except Exception as e:
        print(f"[ERROR] OpenRouter request failed: {e}")
        return "💥 Lumi crashed into a wall of code!"
