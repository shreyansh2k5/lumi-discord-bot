import replicate
import os
import asyncio
from personality import get_temperature

replicate_client = replicate.Client(api_token=os.getenv("REPLICATE_API_TOKEN"))
print("[DEBUG] Loaded Replicate API token:", os.getenv("REPLICATE_API_TOKEN")[:10])

async def query_replicate(prompt: str):
    loop = asyncio.get_event_loop()
    output = await loop.run_in_executor(None, lambda: replicate_client.run(
        "meta/meta-llama-3-8b-instruct",
        input={
            "prompt": prompt,
            "max_new_tokens": 300,
            "temperature": get_temperature()
        }
    ))
    return ''.join(output)
