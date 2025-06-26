import replicate
import os
import asyncio

replicate_client = replicate.Client(api_token=os.getenv("REPLICATE_API_TOKEN"))

async def query_replicate(prompt):
    loop = asyncio.get_event_loop()
    output = await loop.run_in_executor(None, lambda: replicate_client.run(
        "meta/meta-llama-3-8b-instruct",
        input={"prompt": prompt, "max_new_tokens": 300}
    ))
    return ''.join(output)
