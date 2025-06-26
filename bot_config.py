import discord
from replicate_api import query_replicate
from personality import apply_personality
import random

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

MENTION_REPLIES = [
    "Yes? You called me? 💫",
    "Aww, you mentioned me? 😳",
    "What's up, cutie? 😘",
    "You need me? I'm here 💖"
]

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    user_input = message.content.strip()

    # Case 1: !lumi command
    if user_input.startswith("!lumi"):
        query = user_input[len("!lumi"):].strip()
        prompt = apply_personality(query)
        await message.channel.send("💬 Lumi is thinking...")
        response = await query_replicate(prompt)
        await message.channel.send(response)

    # Case 2: Mention
    elif client.user in message.mentions:
        prompt = apply_personality(user_input)
        await message.channel.send(random.choice(MENTION_REPLIES))
        response = await query_replicate(prompt)
        await message.channel.send(response)

    # Case 3: Reply to bot
    elif message.reference:
        replied = await message.channel.fetch_message(message.reference.message_id)
        if replied.author == client.user:
            prompt = apply_personality(user_input)
            await message.channel.send("📝 You replied to me? Let me answer...")
            response = await query_replicate(prompt)
            await message.channel.send(response)

def get_client():
    return client
