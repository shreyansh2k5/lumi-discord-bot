# huggingface_api.py

import os
import requests
from personality import get_temperature

API_TOKEN = os.getenv("HF_API_TOKEN")
MODEL_ID = "HuggingFaceH4/zephyr-7b-beta"

def query_mistral(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "inputs": prompt,
        "parameters": {
            "temperature": get_temperature(),
            "max_new_tokens": 300,
            "do_sample": True
        }
    }

    try:
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{MODEL_ID}",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        if isinstance(data, list) and "generated_text" in data[0]:
            full_text = data[0]["generated_text"].strip()
            print("[DEBUG] Full model response:", full_text)  # optional log

            # Extract only the final "Lumi:" reply
            _, _, last_line = full_text.rpartition("Lumi:")
            last_line = last_line.strip()

            if last_line:
                return last_line[:500]
            else:
                return "💬 Hmm... I didn’t quite catch that. Can you say it again?"
        else:
            print("[DEBUG] Unexpected HF API response:", data)
            return "⚠️ Unexpected Hugging Face response format."

    except requests.exceptions.RequestException as e:
        print("[ERROR] Hugging Face API error:", e)
        return "💥 Lumi is having a brain freeze!"
