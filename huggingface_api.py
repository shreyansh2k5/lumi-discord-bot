# huggingface_api.py

import os
import requests
import aiohttp
from personality import get_temperature

API_TOKEN = os.getenv("HF_API_TOKEN")
MODEL_ID = "HuggingFaceH4/zephyr-7b-beta"

async def query_mistral(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "inputs": prompt,
        "parameters": {
            "temperature": get_temperature(),
            "max_new_tokens": 100,
            "do_sample": True
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://api-inference.huggingface.co/models/{MODEL_ID}",
                headers=headers,
                json=payload,
                timeout=30
            ) as resp:
                if resp.status != 200:
                    print(f"[ERROR] Status: {resp.status}")
                    return "💥 Lumi is having a brain freeze!"
                data = await resp.json()

        if isinstance(data, list) and "generated_text" in data[0]:
            full_text = data[0]["generated_text"].strip()
            _, _, last_line = full_text.rpartition("Lumi:")
            return last_line.strip()[:500] or "💬 Hmm... I didn’t quite catch that. Can you say it again?"

        print("[DEBUG] Unexpected response format:", data)
        return "⚠️ Unexpected Hugging Face response."

    except Exception as e:
        print("[ERROR] Hugging Face API error:", e)
        return "💥 Lumi is having a brain freeze!"
