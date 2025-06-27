# bot_config.py

import discord
import random
from huggingface_api import query_mistral as query_model
from personality import apply_personality

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# 💬 Mention replies — only pick one at a time
MENTION_REPLIES = [
    "Yes? 🌸",
    "You need me? 😊",
    "Hey cutie 💖",
    "Hi there~ ✨"
]

# Track last mention to avoid repetition
last_mention_reply = None

@client.event
async def on_message(message):
    global last_mention_reply

    if message.author == client.user:
        return

    user_input = message.content.strip()

    # Case 1: User @mentions Lumi
    if client.user in message.mentions:
        # Random mention reply, but not repeated
        mention = random.choice([m for m in MENTION_REPLIES if m != last_mention_reply])
        last_mention_reply = mention
        await message.channel.send(mention)

        user_prompt = message.clean_content.replace(f"@{client.user.name}", "").strip()
        if not user_prompt:
            user_prompt = "Say something short and cute!"

        prompt = apply_personality(user_prompt)
        response = query_model(prompt)
        await message.channel.send(response)

    # Case 2: Reply to Lumi's previous message
    elif message.reference:
        replied_msg = await message.channel.fetch_message(message.reference.message_id)
        if replied_msg.author == client.user:
            prompt = apply_personality(user_input)
            await message.channel.send("🖋️ Let me think...")
            response = query_model(prompt)
            await message.channel.send(response)

def get_client():
    return client
