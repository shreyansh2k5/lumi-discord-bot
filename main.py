# main.py

from dotenv import load_dotenv
import os
import discord
from discord import app_commands
from discord.ext.commands import Bot
from bot_config import get_client, revive_chat_loop
from keep_alive import keep_alive
from automod import set_firestore_db
import time

# Firebase Admin SDK imports
import firebase_admin
from firebase_admin import credentials
# Import the asynchronous Firestore client directly
from google.cloud.firestore_v1.async_client import AsyncClient
import json

# CRITICAL FIX: Import load_credentials_from_info from the correct module
from google.oauth2 import service_account

# Optional presence
try:
    from presence import set_rich_presence
except ImportError:
    set_rich_presence = None

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
bot: Bot = get_client()

# Store the start time on the bot object so Cogs can access it
bot.start_time = time.time()

# --- Firebase Initialization ---
FIREBASE_SERVICE_ACCOUNT_KEY_JSON = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")

if not FIREBASE_SERVICE_ACCOUNT_KEY_JSON:
    print("❌ Error: FIREBASE_SERVICE_ACCOUNT_KEY environment variable not set.")
    exit(1)

try:
    service_account_info = json.loads(FIREBASE_SERVICE_ACCOUNT_KEY_JSON)
    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred)
    print("✅ Firebase Admin SDK initialized.")

    project_id = service_account_info.get("project_id")
    auth_credentials = service_account.Credentials.from_service_account_info(service_account_info)

    db = AsyncClient(project=project_id, credentials=auth_credentials)
    set_firestore_db(db)
    print("✅ Asynchronous Firestore client ready.")

except Exception as e:
    print(f"❌ Error initializing Firebase: {e}")
    exit(1)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

    # --- GLOBAL ERROR HANDLER ---
    # This prevents "Application did not respond" for ALL commands
    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            message = f"🚫 You don't have the permissions ({', '.join(error.missing_permissions)}) to use this!"
        elif isinstance(error, app_commands.CommandOnCooldown):
            message = f"⏳ Please wait {error.retry_after:.2f}s before trying again."
        else:
            message = "⚠️ An unexpected error occurred!"
            print(f"Error: {error}")

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    # --- LOAD COGS FROM FOLDER ---
    # We skip __init__.py and load everything else in the folder
    for filename in os.listdir('./slash_commands'):
        if filename.endswith('.py') and filename != '__init__.py':
            try:
                await bot.load_extension(f'slash_commands.{filename[:-3]}')
                print(f"📁 Loaded: {filename}")
            except Exception as e:
                print(f"❌ Failed to load {filename}: {e}")

    # Sync commands with Discord
    await bot.tree.sync()
    print("🌐 Slash commands synced.")

    # Start chat revival loop
    if not revive_chat_loop.is_running():
        revive_chat_loop.start()
        print("💬 Chat revival loop started.")

    # Optional rich presence
    if set_rich_presence:
        try:
            await set_rich_presence(bot)
        except Exception as e:
            print(f"[Warning] Could not set rich presence: {e}")

# Keep the bot alive (replit/hosting) and run
keep_alive()
bot.run(DISCORD_TOKEN)
