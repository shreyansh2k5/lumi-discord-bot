# main.py

from dotenv import load_dotenv
import os
from discord.ext.commands import Bot
from bot_config import get_client
from slash_commands import setup_slash_commands
from keep_alive import keep_alive
# Changed: from automod import initialize_firestore, _load_bad_words_from_firestore
from automod import set_firestore_db # Use the new function to set the db instance

# Firebase Admin SDK imports
import firebase_admin
from firebase_admin import credentials, firestore
import json # Import json to parse the key from environment variable

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
    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred)
    print("✅ Firebase Admin SDK initialized from environment variable.")

    # Get Firestore client
    db = firestore.client()
    print("✅ Firestore client obtained.")

    # Pass the Firestore client to automod module
    set_firestore_db(db) # Use the new setter function
    print("✅ Firestore client passed to automod.py.")

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

    # Removed: Load bad words from Firestore on_ready as it's now per-guild
    # try:
    #     await _load_bad_words_from_firestore()
    # except Exception as e:
    #     print(f"[Bad Words Load Error] Could not load bad words on startup: {e}")

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
