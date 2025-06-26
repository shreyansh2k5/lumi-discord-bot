from dotenv import load_dotenv
import os
from discord import Client
from bot_config import get_client
from keep_alive import keep_alive
from presence import set_rich_presence

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
client: Client = get_client()

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    await set_rich_presence(client)

keep_alive()
client.run(DISCORD_TOKEN)
