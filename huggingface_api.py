# huggingface_api.py
import os, requests
from personality import get_temperature, get_personality_description

API_TOKEN = os.getenv("HF_API_TOKEN")
MODEL_ID = "mistralai/Mistral-7B-Instruct-v0.2"

def query_mistral(prompt: str) -> str:
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "temperature": get_temperature(),
            "max_new_tokens": 300,
            "do_sample": True
        }
    }

    try:
        res = requests.post(
            f"https://api-inference.huggingface.co/models/{MODEL_ID}",
            headers=headers, json=payload
        )
        res.raise_for_status()
        data = res.json()
        return data[0]["generated_text"] if isinstance(data, list) else "⚠️ Unexpected response."
    except Exception as e:
        print("[ERROR] Mistral API error:", e)
        return "💥 Lumi is having a brain freeze!"

