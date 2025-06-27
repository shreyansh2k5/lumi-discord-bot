# huggingface_api.py (Fixed ✅)

import os
import requests
import asyncio
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
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: requests.post(
            f"https://api-inference.huggingface.co/models/{MODEL_ID}",
            headers=headers,
            json=payload,
            timeout=30
        ))
        response.raise_for_status()

        data = response.json()
        if isinstance(data, list) and "generated_text" in data[0]:
            full_text = data[0]["generated_text"].strip()
            print("[DEBUG] Full model response:", full_text)

            # Get the last line after "Lumi:"
            _, _, last_line = full_text.rpartition("Lumi:")
            return last_line.strip()[:500] or "💬 Hmm... I didn’t quite catch that. Can you say it again?"
        else:
            print("[DEBUG] Unexpected HF API response:", data)
            return "⚠️ Unexpected Hugging Face response format."

    except requests.exceptions.RequestException as e:
        print("[ERROR] Hugging Face API error:", e)
        return "💥 Lumi is having a brain freeze!"
