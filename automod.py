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

# --- Bad words (now stored in Firestore) ---
# We'll fetch this from Firestore on startup and keep a local cache for quick checks
_cached_bad_words = set()

async def _load_bad_words_from_firestore():
    """Loads bad words from Firestore into a local cache."""
    global _cached_bad_words
    if db is None:
        print("Firestore DB not initialized in automod.py. Cannot load bad words.")
        return

    try:
        doc_ref = db.collection('global_settings').document('moderation')
        doc = await doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            _cached_bad_words = set(data.get('bad_words', []))
            print(f"Loaded {len(_cached_bad_words)} bad words from Firestore.")
        else:
            print("No bad words document found in Firestore. Starting with empty list.")
            _cached_bad_words = set()
    except Exception as e:
        print(f"Error loading bad words from Firestore: {e}")
        _cached_bad_words = set() # Fallback to empty set on error

async def _save_bad_words_to_firestore():
    """Saves the current bad words cache to Firestore."""
    if db is None:
        print("Firestore DB not initialized in automod.py. Cannot save bad words.")
        return

    try:
        doc_ref = db.collection('global_settings').document('moderation')
        await doc_ref.set({'bad_words': list(_cached_bad_words)})
        print(f"Saved {len(_cached_bad_words)} bad words to Firestore.")
    except Exception as e:
        print(f"Error saving bad words to Firestore: {e}")

# --- Exception Roles (now stored in Firestore per guild) ---

# This will be fetched on demand or cached per guild as needed.
# For simplicity, we'll fetch per guild when checking/modifying.

# 🚨 Bad word checker
def check_bad_words(message: str) -> bool:
    """Checks if the message contains any cached bad words."""
    message = message.lower()
    return any(bad_word in message for bad_word in _cached_bad_words)

# --- Functions for managing bad words (Firestore-backed) ---

async def add_bad_word(word: str) -> bool:
    """Adds a word to the global bad_words set in Firestore."""
    word = word.lower()
    if word not in _cached_bad_words:
        _cached_bad_words.add(word)
        await _save_bad_words_to_firestore()
        return True
    return False

async def remove_bad_word(word: str) -> bool:
    """Removes a word from the global bad_words set in Firestore."""
    word = word.lower()
    if word in _cached_bad_words:
        _cached_bad_words.remove(word)
        await _save_bad_words_to_firestore()
        return True
    return False

async def get_bad_words() -> list[str]:
    """Returns a sorted list of all current bad words from cache."""
    return sorted(list(_cached_bad_words))

# --- Functions for managing exception roles (Firestore-backed) ---

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
        await doc_ref.set({'exempt_roles': list(roles)})
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
