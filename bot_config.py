# bot_config.py (Fresh, without !lumi feature)

import discord
from huggingface_api import query_mistral as query_model
from personality import apply_personality
import random

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

MENTION_REPLIES = [
    "Yes? You called me? 🌟",
    "Aww, you mentioned me? 😳",
    "What's up, cutie? 😝",
    "You need me? I'm here 💖"
]

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    user_input = message.content.strip()

    # Case 1: Mention
    if client.user in message.mentions:
        mention_reply = random.choice(MENTION_REPLIES)
        await message.channel.send(mention_reply)

        # Remove mention from prompt
        user_prompt = message.clean_content.replace(f"@{client.user.name}", "").strip()
        if not user_prompt:
            user_prompt = "Say something cute!"

        prompt = apply_personality(user_prompt)
        response = query_model(prompt)
        await message.channel.send(response)

    # Case 2: Reply to Lumi
    elif message.reference:
        replied = await message.channel.fetch_message(message.reference.message_id)
        if replied.author == client.user:
            prompt = apply_personality(user_input)
            await message.channel.send("🖋️ You replied to me? Let me answer...")
            response = query_model(prompt)
            await message.channel.send(response)

def get_client():
    return client
