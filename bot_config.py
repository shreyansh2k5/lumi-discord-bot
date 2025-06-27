# bot_config.py

import discord
from huggingface_api import query_mistral as query_model
from personality import apply_personality

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    user_input = message.content.strip()

    # Case 1: Mentioned Lumi
    if client.user in message.mentions:
        user_prompt = message.clean_content.replace(f"@{client.user.name}", "").strip()
        if not user_prompt:
            user_prompt = "Say something cute!"

        prompt = apply_personality(user_prompt)
        response = await query_model(prompt)  # ✅ FIXED: Added await
        await message.channel.send(response)

    # Case 2: Replying to Lumi
    elif message.reference:
        replied_msg = await message.channel.fetch_message(message.reference.message_id)
        if replied_msg.author == client.user:
            prompt = apply_personality(user_input)
            await message.channel.send("🖋️ You replied to me? Let me think...")
            response = await query_model(prompt)  # ✅ FIXED: Added await
            await message.channel.send(response)

def get_client():
    return client
