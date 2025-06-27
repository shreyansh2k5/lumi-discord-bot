# main.py

from dotenv import load_dotenv
import os
from discord import Client
from bot_config import get_client
from keep_alive import keep_alive

# Optional presence
try:
    from presence import set_rich_presence
except ImportError:
    set_rich_presence = None

# Load .env file
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
client: Client = get_client()

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    if set_rich_presence:
        try:
            await set_rich_presence(client)
        except Exception as e:
            print(f"[Warning] Could not set rich presence: {e}")

keep_alive()
client.run(DISCORD_TOKEN)
