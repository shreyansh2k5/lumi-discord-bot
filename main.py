import discord
import os
import openai
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Set up Discord bot intents
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

# Set OpenRouter credentials
openai.api_key = OPENROUTER_API_KEY
openai.api_base = "https://openrouter.ai/api/v1"

# Function to query OpenRouter (Mistral 24B)
def query_openrouter(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="mistralai/mistral-small-3.2-24b-instruct",
            messages=[
                {"role": "system", "content": "You are Lumi, a flirty, playful anime girl who uses lots of emojis like 💕😚. You speak casually and tease the user sometimes."},
                {"role": "user", "content": prompt}
            ]
        )
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        print("Error from OpenRouter:", e)
        return f"⚠️ Error: {e}"

# Bot is ready
@bot.event
async def on_ready():
    print(f"💫 LUMI is online as {bot.user}")

# Handle messages (mention or reply)
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    mentioned = bot.user in message.mentions
    is_reply = message.reference is not None and (
        (await message.channel.fetch_message(message.reference.message_id)).author == bot.user
    )

    if mentioned or is_reply:
        prompt = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if not prompt:
            prompt = "Say something cute to me!"
        reply = query_openrouter(prompt)
        await message.channel.send(reply)
