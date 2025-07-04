# main.py

from dotenv import load_dotenv
import os
from discord.ext.commands import Bot
from bot_config import get_client
from slash_commands import setup_slash_commands
from keep_alive import keep_alive
from automod import set_firestore_db

# Firebase Admin SDK imports
import firebase_admin
from firebase_admin import credentials
# Import the asynchronous Firestore client directly
from google.cloud.firestore_v1.async_client import AsyncClient
import json

# Import google.auth for explicit credentials
import google.auth


# Optional presence
try:
    from presence import set_rich_presence
except ImportError:
    set_rich_presence = None

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
bot: Bot = get_client()

# --- Firebase Initialization ---
# Retrieve the service account key from environment variable
FIREBASE_SERVICE_ACCOUNT_KEY_JSON = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")

if not FIREBASE_SERVICE_ACCOUNT_KEY_JSON:
    print("❌ Error: FIREBASE_SERVICE_ACCOUNT_KEY environment variable not set.")
    print("Please set this environment variable with the content of your serviceAccountKey.json file.")
    exit(1)

try:
    # Parse the JSON string from the environment variable
    service_account_info = json.loads(FIREBASE_SERVICE_ACCOUNT_KEY_JSON)

    # Initialize Firebase Admin SDK (still synchronous)
    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred)
    print("✅ Firebase Admin SDK initialized from environment variable.")

    # Extract project_id from service_account_info
    project_id = service_account_info.get("project_id")
    if not project_id:
        raise ValueError("project_id not found in service account key JSON.")

    # Create google-auth credentials from the service account info
    # This is the standard way to create credentials for google-cloud-* libraries
    auth_credentials, project = google.auth.load_credentials_from_info(service_account_info)

    # Initialize the ASYNCHRONOUS Firestore client directly
    # Pass the project ID and the created credentials explicitly
    db = AsyncClient(project=project_id, credentials=auth_credentials)
    print("✅ Asynchronous Firestore client obtained with explicit credentials.")

    # Pass the Async Firestore client to automod module
    set_firestore_db(db)
    print("✅ Asynchronous Firestore client passed to automod.py.")

except json.JSONDecodeError as e:
    print(f"❌ Error decoding Firebase service account JSON from environment variable: {e}")
    print("Please ensure the FIREBASE_SERVICE_ACCOUNT_KEY environment variable contains valid JSON.")
    exit(1)
except Exception as e:
    print(f"❌ Error initializing Firebase: {e}")
    exit(1)


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

    # ✅ Optional rich presence
    if set_rich_presence:
        try:
            await set_rich_presence(bot)
        except Exception as e:
            print(f"[Warning] Could not set rich presence: {e}")

keep_alive()
bot.run(DISCORD_TOKEN)
