import discord
from replicate_api import query_replicate
from personality import apply_personality

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.startswith("!lumi"):
        user_input = message.content[len("!lumi "):].strip()
        prompt = apply_personality(user_input)

        await message.channel.send("💬 Lumi is thinking...")
        response = await query_replicate(prompt)
        await message.channel.send(response)

def get_client():
    return client

