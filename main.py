# main.py

from dotenv import load_dotenv
import os
from discord.ext.commands import Bot
from bot_config import get_client
from slash_commands import setup_slash_commands
from keep_alive import keep_alive
from mention_commands import setup_mention_commands


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

    # ✅ Setup and sync slash commands
    try:
        await setup_slash_commands(bot)
        await bot.tree.sync()
        print("🌐 Slash commands synced.")
    except Exception as e:
        print(f"[Slash Sync Error] {e}")

    # ✅ Setup mention-based commands and moderation listeners
    try:
        setup_mention_commands(bot)
        print("💬 Mention commands and moderation listeners set up.")
    except Exception as e:
        print(f"[Mention Commands Setup Error] {e}")


    # ✅ Optional rich presence
    if set_rich_presence:
        try:
            await set_rich_presence(bot)
        except Exception as e:
            print(f"[Warning] Could not set rich presence: {e}")

keep_alive()
bot.run(DISCORD_TOKEN)
