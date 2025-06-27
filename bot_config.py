# bot_config.py

import discord
import random
from huggingface_api import query_mistral as query_model
from personality import apply_personality

# Enable message content intent
intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# 💬 Fun response when Lumi is mentioned
MENTION_REPLIES = [
    "Yes? You called me? 🌸",
    "Aww, you mentioned me? 😳",
    "What’s up, cutie? 💕",
    "Need me? I’m right here! ✨"
]

@client.event
async def on_message(message):
    # Ignore bot’s own messages
    if message.author == client.user:
        return

    user_input = message.content.strip()

    # Case 1: Direct mention of Lumi
    if client.user in message.mentions:
        await message.channel.send(random.choice(MENTION_REPLIES))

        # Remove the @mention from prompt text
        user_prompt = message.clean_content.replace(f"@{client.user.name}", "").strip()
        if not user_prompt:
            user_prompt = "Say something cute!"

        prompt = apply_personality(user_prompt)
        response = query_model(prompt)
        await message.channel.send(response)

    # Case 2: Replying to Lumi's previous message
    elif message.reference:
        replied_msg = await message.channel.fetch_message(message.reference.message_id)
        if replied_msg.author == client.user:
            prompt = apply_personality(user_input)
            await message.channel.send("🖋️ You replied to me? Let me think...")
            response = query_model(prompt)
            await message.channel.send(response)

# Export client so main.py can use it
def get_client():
    return client
