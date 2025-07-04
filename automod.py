# automod.py

import firebase_admin
from firebase_admin import credentials, firestore
import json

# Global Firestore client instance (will be set by main.py)
_firestore_db_instance = None

def set_firestore_db(firestore_client):
    """Sets the global Firestore client instance for this module."""
    global _firestore_db_instance
    _firestore_db_instance = firestore_client
    print("Firestore client instance set in automod.py")

# 🚨 Bad word checker (now requires guild_id)
async def check_bad_words(message: str, guild_id: int) -> bool:
    """Checks if the message contains any bad words for the specific guild."""
    if _firestore_db_instance is None:
        print("DEBUG: Firestore DB not set in check_bad_words. Cannot check bad words.")
        return False

    message = message.lower()
    # Ensure this call is awaited
    guild_bad_words = await _get_guild_bad_words_from_firestore(guild_id)
    print(f"DEBUG: check_bad_words - Guild {guild_id} current bad words: {guild_bad_words}")
    return any(bad_word in message for bad_word in guild_bad_words)

# --- Functions for managing bad words (Firestore-backed, per-guild) ---

async def _get_guild_bad_words_from_firestore(guild_id: int) -> set[str]:
    """Fetches bad words for a specific guild from Firestore."""
    if _firestore_db_instance is None:
        print("DEBUG: Firestore DB not set in _get_guild_bad_words_from_firestore. Cannot fetch guild bad words.")
        return set()

    try:
        doc_ref = _firestore_db_instance.collection('guilds').document(str(guild_id))
        # CRITICAL FIX: AWAIT THE GET OPERATION
        doc = await doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            retrieved_words = set(data.get('bad_words', []))
            print(f"DEBUG: Fetched bad words for guild {guild_id}: {retrieved_words}")
            return retrieved_words
        print(f"DEBUG: No bad words document found for guild {guild_id}.")
        return set()
    except Exception as e:
        print(f"ERROR: Error fetching bad words for guild {guild_id}: {e}")
        return set()

async def _save_guild_bad_words_to_firestore(guild_id: int, words: set[str]):
    """Saves bad words for a specific guild to Firestore."""
    if _firestore_db_instance is None:
        print("DEBUG: Firestore DB not set in _save_guild_bad_words_to_firestore. Cannot save guild bad words.")
        return

    try:
        doc_ref = _firestore_db_instance.collection('guilds').document(str(guild_id))
        data_to_save = {'bad_words': list(words)} # Convert set to list for Firestore
        # Ensure this call is awaited
        await doc_ref.set(data_to_save, merge=True)
        print(f"DEBUG: Saved bad words for guild {guild_id}: {words}")
    except Exception as e:
        print(f"ERROR: Error saving bad words to Firestore for guild {guild_id}: {e}")

async def add_bad_word(word: str, guild_id: int) -> bool:
    """Adds a word to the bad_words set for a specific guild in Firestore."""
    word = word.lower()
    current_bad_words = await _get_guild_bad_words_from_firestore(guild_id)
    if word not in current_bad_words:
        current_bad_words.add(word)
        await _save_guild_bad_words_to_firestore(guild_id, current_bad_words)
        print(f"DEBUG: Added '{word}' to guild {guild_id}'s bad words. New set: {current_bad_words}")
        return True
    print(f"DEBUG: '{word}' already exists in guild {guild_id}'s bad words.")
    return False

async def remove_bad_word(word: str, guild_id: int) -> bool:
    """Removes a word from the bad_words set for a specific guild in Firestore."""
    word = word.lower()
    current_bad_words = await _get_guild_bad_words_from_firestore(guild_id)
    if word in current_bad_words:
        current_bad_words.remove(word)
        await _save_guild_bad_words_to_firestore(guild_id, current_bad_words)
        print(f"DEBUG: Removed '{word}' from guild {guild_id}'s bad words. New set: {current_bad_words}")
        return True
    print(f"DEBUG: '{word}' not found in guild {guild_id}'s bad words.")
    return False

async def get_bad_words(guild_id: int) -> list[str]:
    """Returns a sorted list of all current bad words for a specific guild from Firestore."""
    current_bad_words = await _get_guild_bad_words_from_firestore(guild_id)
    print(f"DEBUG: get_bad_words for guild {guild_id} returning: {sorted(list(current_bad_words))}")
    return sorted(list(current_bad_words))

# --- Functions for managing exception roles (Firestore-backed, per-guild) ---

async def _get_guild_exempt_roles_from_firestore(guild_id: int) -> set[str]:
    """Fetches exempt roles for a specific guild from Firestore."""
    if _firestore_db_instance is None:
        print("DEBUG: Firestore DB not set. Cannot fetch exempt roles.")
        return set()

    try:
        doc_ref = _firestore_db_instance.collection('guilds').document(str(guild_id))
        # CRITICAL FIX: AWAIT THE GET OPERATION
        doc = await doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            retrieved_roles = set(data.get('exempt_roles', []))
            print(f"DEBUG: Fetched exempt roles for guild {guild_id}: {retrieved_roles}")
            return retrieved_roles
        print(f"DEBUG: No exempt roles document found for guild {guild_id}.")
        return set()
    except Exception as e:
        print(f"ERROR: Error fetching exempt roles for guild {guild_id}: {e}")
        return set()

async def _save_guild_exempt_roles_to_firestore(guild_id: int, roles: set[str]):
    """Saves exempt roles for a specific guild to Firestore."""
    if _firestore_db_instance is None:
        print("DEBUG: Firestore DB not set. Cannot save exempt roles.")
        return

    try:
        doc_ref = _firestore_db_instance.collection('guilds').document(str(guild_id))
        data_to_save = {'exempt_roles': list(roles)}
        # Ensure this call is awaited
        await doc_ref.set(data_to_save, merge=True)
        print(f"DEBUG: Saved exempt roles for guild {guild_id}: {roles}")
    except Exception as e:
        print(f"ERROR: Error saving exempt roles for guild {guild_id}: {e}")

async def add_exception_role(guild_id: int, role_name: str):
    """Adds an exception role for a guild and saves to Firestore."""
    current_roles = await _get_guild_exempt_roles_from_firestore(guild_id)
    if role_name not in current_roles:
        current_roles.add(role_name)
        await _save_guild_exempt_roles_to_firestore(guild_id, current_roles)
        print(f"DEBUG: Added '{role_name}' to guild {guild_id}'s exempt roles. New set: {current_roles}")
        return True
    print(f"DEBUG: '{role_name}' already exists in guild {guild_id}'s exempt roles.")
    return False

async def remove_exception_role(guild_id: int, role_name: str):
    """Removes an exception role for a guild and saves to Firestore."""
    current_roles = await _get_guild_exempt_roles_from_firestore(guild_id)
    if role_name in current_roles:
        current_roles.remove(role_name)
        await _save_guild_exempt_roles_to_firestore(guild_id, current_roles)
        print(f"DEBUG: Removed '{role_name}' from guild {guild_id}'s exempt roles. New set: {current_roles}")
        return True
    print(f"DEBUG: '{role_name}' not found in guild {guild_id}'s exempt roles.")
    return False

async def is_role_exempt(guild_id: int, role_name: str) -> bool:
    """Checks if a role is exempt for a guild from Firestore."""
    current_roles = await _get_guild_exempt_roles_from_firestore(guild_id)
    return role_name in current_roles

async def get_exempt_roles(guild_id: int) -> list[str]:
    """Returns a list of exempt roles for a guild from Firestore."""
    current_roles = await _get_guild_exempt_roles_from_firestore(guild_id)
    print(f"DEBUG: get_exempt_roles for guild {guild_id} returning: {sorted(list(current_roles))}")
    return sorted(list(current_roles))
