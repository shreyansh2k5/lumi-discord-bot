# bot_config.py

import discord
import random
from huggingface_api import query_mistral as query_model
from personality import apply_personality

# Enable message content intent
intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# 💬 Reply variations when Lumi is mentioned
MENTION_REPLIES = [
    "Yes? You called me? 🌸",
    "Aww, you mentioned me? 😳",
    "What’s up, cutie? 💕",
    "Need me? I’m right here! ✨"
]

MAX_RESPONSE_LENGTH = 300  # Trim long replies

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    user_input = message.content.strip()

    # Case 1: Mentioning Lumi
    if client.user in message.mentions:
        await message.channel.send(random.choice(MENTION_REPLIES))

        # Clean @mention from prompt
        user_prompt = message.clean_content.replace(f"@{client.user.name}", "").strip()
        if not user_prompt:
            user_prompt = "Say something cute!"

        prompt = apply_personality(user_prompt)
        response = await query_model(prompt)

        # Trim and send reply
        reply = response.strip().split("\n")[0][:MAX_RESPONSE_LENGTH]
        await message.channel.send(reply or "💬 I didn’t get that, try again?")

    # Case 2: Replying to Lumi’s previous message
    elif message.reference:
        replied_msg = await message.channel.fetch_message(message.reference.message_id)
        if replied_msg.author == client.user:
            prompt = apply_personality(user_input)
            await message.channel.send("🖋️ You replied to me? Let me think...")

            response = await query_model(prompt)
            reply = response.strip().split("\n")[0][:MAX_RESPONSE_LENGTH]
            await message.channel.send(reply or "💬 I didn’t get that, try again?")

# Export client for main.py
def get_client():
    return client
