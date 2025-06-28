# main.py

from dotenv import load_dotenv
import os
from discord.ext.commands import Bot
from bot_config import get_client
from keep_alive import keep_alive

# Optional presence
try:
    from presence import set_rich_presence
except ImportError:
    set_rich_presence = None

# Load environment variables
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
bot: Bot = get_client()

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    if set_rich_presence:
        try:
            await set_rich_presence(bot)
        except Exception as e:
            print(f"[Warning] Could not set rich presence: {e}")

keep_alive()
bot.run(DISCORD_TOKEN)
