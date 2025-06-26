import discord
import os
import requests
from dotenv import load_dotenv

# ✅ Tell Render we're running without a port
os.environ["RENDER"] = "true"

# ✅ Fake HTTP server to keep Render happy
from threading import Thread
from http.server import HTTPServer, SimpleHTTPRequestHandler

def keep_alive():
    server = HTTPServer(("0.0.0.0", 8080), SimpleHTTPRequestHandler)
    server.serve_forever()

Thread(target=keep_alive).start()

# ✅ Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ✅ Discord setup
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
bot = discord.Client(intents=intents)

# ✅ memory 
def ask_openrouter(user_id, prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    # Get memory
    memory = user_memory[user_id]
    messages = [{"role": "system", "content": "You are Lumi, a flirty anime girl Discord bot. You reply with charm, playfulness, and heart emojis."}]
    
    for m in memory:
        messages.append({"role": "user", "content": m["user"]})
        messages.append({"role": "assistant", "content": m["bot"]})
    
    # Append current prompt
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": "mistralai/mistral-small-3.2-24b-instruct:free",
        "messages": messages
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        bot_reply = response.json()["choices"][0]["message"]["content"]
        
        # Save to memory
        user_memory[user_id].append({"user": prompt, "bot": bot_reply})
        return bot_reply

    except Exception as e:
        return f"⚠️ Error: {e}"


# ✅ Bot events
@bot.event
async def on_ready():
    print(f"🤖 Lumi is online as {bot.user}")

    # 🎮 Rich presence setup
    activity = discord.Activity(
        type=discord.ActivityType.watching,  # Change this to .playing, .listening, .competing
        name=" In ur heart 💖"
    )
    await bot.change_presence(status=discord.Status.idle, activity=activity)



@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    mentioned = bot.user in message.mentions
    replied_to_bot = message.reference and message.reference.resolved and message.reference.resolved.author == bot.user

    if mentioned or replied_to_bot:
        prompt = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if not prompt:
            prompt = "Hey Lumi!"  # fallback
        reply = ask_openrouter(message.author.id, prompt)
        await message.channel.send(reply)
        
# ✅ Load all cogs from /cogs
async def load_extensions():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")
            
bot.loop.create_task(load_extensions())            
bot.run(DISCORD_TOKEN)
