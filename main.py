import discord
import os
import requests
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HF_API_KEY = os.getenv("HF_API_KEY")

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

def query_huggingface(prompt):
    API_URL = "https://api-inference.huggingface.co/models/tiiuae/falcon-rw-1b"
    headers = {"Authorization": f"Bearer " + HF_API_KEY}
    payload = {"inputs": prompt}
    response = requests.post(API_URL, headers=headers, json=payload)
    try:
        return response.json()[0]['generated_text']
    except Exception as e:
        return f"⚠️ Error: {e}"

@bot.event
async def on_ready():
    print(f"🤖 LUMI is online as {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if message.content.startswith("!ask"):
        prompt = message.content[5:].strip()
        if prompt:
            reply = query_huggingface(prompt)
            await message.channel.send(reply)

bot.run(DISCORD_TOKEN)
