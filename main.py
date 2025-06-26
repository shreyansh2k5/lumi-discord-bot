import os
import discord
import requests
from dotenv import load_dotenv
from discord.ext import commands
from threading import Thread
from http.server import HTTPServer, SimpleHTTPRequestHandler

# ✅ Tell Render we're running without a port
os.environ["RENDER"] = "true"

# ✅ Fake HTTP server to keep Render happy
def keep_alive():
    server = HTTPServer(("0.0.0.0", 8080), SimpleHTTPRequestHandler)
    server.serve_forever()

Thread(target=keep_alive).start()

# ✅ Load .env variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ✅ Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)  # Slash commands don't use the prefix

# ✅ In-memory conversation history
user_memory = {}

def ask_openrouter(user_id, prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    if user_id not in user_memory:
        user_memory[user_id] = []

    memory = user_memory[user_id]
    messages = [{"role": "system", "content": "You are Lumi, a flirty anime girl Discord bot. You reply with charm, playfulness, and heart emojis."}]

    for m in memory:
        messages.append({"role": "user", "content": m["user"]})
        messages.append({"role": "assistant", "content": m["bot"]})

    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": "meta-llama/llama-3.1-8b-instruct:free",
        "messages": messages
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        bot_reply = response.json()["choices"][0]["message"]["content"]
        user_memory[user_id].append({"user": prompt, "bot": bot_reply})
        return bot_reply
    except Exception as e:
        return f"⚠️ Error: {e}"

# ✅ Bot events
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"🤖 Lumi is online as {bot.user}")
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="In ur heart 💖"
    )
    await bot.change_presence(status=discord.Status.idle, activity=activity)

# ✅ Mention/reply chat behavior
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    mentioned = bot.user in message.mentions
    replied_to_bot = message.reference and message.reference.resolved and message.reference.resolved.author == bot.user

    if mentioned or replied_to_bot:
        prompt = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if not prompt:
            prompt = "Hey Lumi!"  # Fallback if no actual message
        reply = ask_openrouter(message.author.id, prompt)
        await message.channel.send(reply)

    await bot.process_commands(message)  # Important for slash commands to work with on_message

# ✅ Load all cogs in /cogs
async def load_extensions():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")

bot.loop.create_task(load_extensions())
bot.run(DISCORD_TOKEN)
