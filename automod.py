# automod.py

import firebase_admin
from firebase_admin import credentials, firestore
import json # Still needed for potential JSON serialization if complex objects are stored

# Global Firestore client instance
db = None

def initialize_firestore(firestore_client):
    """Initializes the Firestore client for this module."""
    global db
    db = firestore_client
    print("Firestore client initialized in automod.py")

# --- NO MORE GLOBAL _cached_bad_words SET ---
# Bad words will be fetched per guild when needed.
# The initial _load_bad_words_from_firestore() call is also removed from main.py
# as it's no longer global.

# 🚨 Bad word checker (now requires guild_id)
async def check_bad_words(message: str, guild_id: int) -> bool:
    """Checks if the message contains any bad words for the specific guild."""
    if db is None:
        print("Firestore DB not initialized. Cannot check bad words.")
        return False

    message = message.lower()
    guild_bad_words = await _get_guild_bad_words_from_firestore(guild_id)
    return any(bad_word in message for bad_word in guild_bad_words)

# --- Functions for managing bad words (Firestore-backed, per-guild) ---

async def _get_guild_bad_words_from_firestore(guild_id: int) -> set[str]:
    """Fetches bad words for a specific guild from Firestore."""
    if db is None:
        print("Firestore DB not initialized. Cannot fetch guild bad words.")
        return set()

    try:
        doc_ref = db.collection('guilds').document(str(guild_id))
        doc = await doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            return set(data.get('bad_words', []))
        return set()
    except Exception as e:
        print(f"Error fetching bad words for guild {guild_id}: {e}")
        return set()

async def _save_guild_bad_words_to_firestore(guild_id: int, words: set[str]):
    """Saves bad words for a specific guild to Firestore."""
    if db is None:
        print("Firestore DB not initialized. Cannot save guild bad words.")
        return

    try:
        doc_ref = db.collection('guilds').document(str(guild_id))
        # Use merge=True to only update the 'bad_words' field without overwriting other fields
        await doc_ref.set({'bad_words': list(words)}, merge=True)
    except Exception as e:
        print(f"Error saving bad words for guild {guild_id}: {e}")

async def add_bad_word(word: str, guild_id: int) -> bool:
    """Adds a word to the bad_words set for a specific guild in Firestore."""
    word = word.lower()
    current_bad_words = await _get_guild_bad_words_from_firestore(guild_id)
    if word not in current_bad_words:
        current_bad_words.add(word)
        await _save_guild_bad_words_to_firestore(guild_id, current_bad_words)
        return True
    return False

async def remove_bad_word(word: str, guild_id: int) -> bool:
    """Removes a word from the bad_words set for a specific guild in Firestore."""
    word = word.lower()
    current_bad_words = await _get_guild_bad_words_from_firestore(guild_id)
    if word in current_bad_words:
        current_bad_words.remove(word)
        await _save_guild_bad_words_to_firestore(guild_id, current_bad_words)
        return True
    return False

async def get_bad_words(guild_id: int) -> list[str]:
    """Returns a sorted list of all current bad words for a specific guild from Firestore."""
    current_bad_words = await _get_guild_bad_words_from_firestore(guild_id)
    return sorted(list(current_bad_words))

# --- Functions for managing exception roles (Firestore-backed, per-guild) ---
# These remain largely the same, but are included for completeness and context.

async def _get_guild_exempt_roles_from_firestore(guild_id: int) -> set[str]:
    """Fetches exempt roles for a specific guild from Firestore."""
    if db is None:
        print("Firestore DB not initialized. Cannot fetch exempt roles.")
        return set()

    try:
        doc_ref = db.collection('guilds').document(str(guild_id))
        doc = await doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            return set(data.get('exempt_roles', []))
        return set()
    except Exception as e:
        print(f"Error fetching exempt roles for guild {guild_id}: {e}")
        return set()

async def _save_guild_exempt_roles_to_firestore(guild_id: int, roles: set[str]):
    """Saves exempt roles for a specific guild to Firestore."""
    if db is None:
        print("Firestore DB not initialized. Cannot save exempt roles.")
        return

    try:
        doc_ref = db.collection('guilds').document(str(guild_id))
        # Use merge=True to only update the 'exempt_roles' field without overwriting other fields
        await doc_ref.set({'exempt_roles': list(roles)}, merge=True)
    except Exception as e:
        print(f"Error saving exempt roles for guild {guild_id}: {e}")

async def add_exception_role(guild_id: int, role_name: str):
    """Adds an exception role for a guild and saves to Firestore."""
    current_roles = await _get_guild_exempt_roles_from_firestore(guild_id)
    if role_name not in current_roles:
        current_roles.add(role_name)
        await _save_guild_exempt_roles_to_firestore(guild_id, current_roles)
        return True
    return False

async def remove_exception_role(guild_id: int, role_name: str):
    """Removes an exception role for a guild and saves to Firestore."""
    current_roles = await _get_guild_exempt_roles_from_firestore(guild_id)
    if role_name in current_roles:
        current_roles.remove(role_name)
        await _save_guild_exempt_roles_to_firestore(guild_id, current_roles)
        return True
    return False

async def is_role_exempt(guild_id: int, role_name: str) -> bool:
    """Checks if a role is exempt for a guild from Firestore."""
    current_roles = await _get_guild_exempt_roles_from_firestore(guild_id)
    return role_name in current_roles

async def get_exempt_roles(guild_id: int) -> list[str]:
    """Returns a list of exempt roles for a guild from Firestore."""
    current_roles = await _get_guild_exempt_roles_from_firestore(guild_id)
    return sorted(list(current_roles))
