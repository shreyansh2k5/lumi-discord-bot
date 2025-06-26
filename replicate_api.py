import replicate
import os
import asyncio
from personality import get_temperature, get_personality_description  # make sure both are imported

replicate_client = replicate.Client(api_token=os.getenv("REPLICATE_API_TOKEN"))

async def query_replicate(prompt: str):
    loop = asyncio.get_event_loop()
    try:
        output = await loop.run_in_executor(None, lambda: replicate_client.run(
            "meta/meta-llama-3-8b-instruct",
            input={
                "prompt": prompt,
                "system_prompt": get_personality_description(),  # ✨ THIS IS NEW
                "max_new_tokens": 300,
                "temperature": get_temperature()
            }
        ))
        return ''.join(output) if isinstance(output, list) else str(output)
    except Exception as e:
        print("[ERROR] Failed to query Replicate:", str(e))
        return "I'm having trouble thinking right now 💥"
