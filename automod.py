# automod.py

import firebase_admin
from firebase_admin import credentials, firestore
import json

# Global Firestore client instance (will be set by main.py)
_firestore_db_instance = None

# In-memory cache for guild settings (bad_words and exempt_roles)
# Structure: {guild_id: {'bad_words': set(), 'exempt_roles': set()}}
_guild_settings_cache = {}

def set_firestore_db(firestore_client):
    """Sets the global Firestore client instance for this module."""
    global _firestore_db_instance
    _firestore_db_instance = firestore_client
    print("Firestore client instance set in automod.py")

async def _load_guild_settings_from_firestore(guild_id: int):
    """
    Loads all settings (bad words and exempt roles) for a specific guild from Firestore
    and updates the in-memory cache.
    """
    if _firestore_db_instance is None:
        print("DEBUG: Firestore DB not set in _load_guild_settings_from_firestore. Cannot load settings.")
        return

    try:
        doc_ref = _firestore_db_instance.collection('guilds').document(str(guild_id))
        doc = await doc_ref.get() # Await the get operation
        
        settings = {'bad_words': set(), 'exempt_roles': set()}
        if doc.exists:
            data = doc.to_dict()
            settings['bad_words'] = set(data.get('bad_words', []))
            settings['exempt_roles'] = set(data.get('exempt_roles', []))
            print(f"DEBUG: Loaded settings for guild {guild_id} from Firestore: {settings}")
        else:
            print(f"DEBUG: No settings document found for guild {guild_id}. Initializing empty settings.")
        
        _guild_settings_cache[guild_id] = settings
    except Exception as e:
        print(f"ERROR: Error loading settings for guild {guild_id} from Firestore: {e}")
        # Fallback to empty settings in cache on error
        _guild_settings_cache[guild_id] = {'bad_words': set(), 'exempt_roles': set()}

async def _save_guild_settings_to_firestore(guild_id: int):
    """
    Saves the current in-memory cache for a specific guild to Firestore.
    """
    if _firestore_db_instance is None:
        print("DEBUG: Firestore DB not set in _save_guild_settings_to_firestore. Cannot save settings.")
        return
    if guild_id not in _guild_settings_cache:
        print(f"DEBUG: Guild {guild_id} not in cache, nothing to save to Firestore.")
        return

    try:
        doc_ref = _firestore_db_instance.collection('guilds').document(str(guild_id))
        settings_to_save = {
            'bad_words': list(_guild_settings_cache[guild_id]['bad_words']),
            'exempt_roles': list(_guild_settings_cache[guild_id]['exempt_roles'])
        }
        await doc_ref.set(settings_to_save, merge=True) # Await the set operation
        print(f"DEBUG: Saved settings for guild {guild_id} to Firestore: {settings_to_save}")
    except Exception as e:
        print(f"ERROR: Error saving settings for guild {guild_id} to Firestore: {e}")

# Helper to ensure guild settings are in cache (publicly callable now)
async def ensure_guild_settings_in_cache(guild_id: int):
    """
    Ensures guild settings are loaded into cache.
    To be called ONCE at the start of an event handler that needs guild settings.
    """
    if guild_id not in _guild_settings_cache:
        await _load_guild_settings_from_firestore(guild_id)

# 🚨 Bad word checker (now accepts guild_settings directly)
def check_bad_words(message: str, guild_id: int, guild_settings: dict) -> bool:
    """Checks if the message contains any bad words for the specific guild, using provided settings."""
    message = message.lower()
    guild_bad_words = guild_settings['bad_words']
    print(f"DEBUG: check_bad_words - Guild {guild_id} current bad words from cache: {guild_bad_words}")
    return any(bad_word in message for bad_word in guild_bad_words)

# --- Functions for managing bad words (now accept guild_settings directly) ---

async def add_bad_word(word: str, guild_id: int, guild_settings: dict) -> bool:
    """Adds a word to the bad_words set for a specific guild, updates cache and Firestore."""
    word = word.lower()
    if word not in guild_settings['bad_words']:
        guild_settings['bad_words'].add(word)
        await _save_guild_settings_to_firestore(guild_id)
        print(f"DEBUG: Added '{word}' to guild {guild_id}'s bad words. New cache set: {guild_settings['bad_words']}")
        return True
    print(f"DEBUG: '{word}' already exists in guild {guild_id}'s bad words.")
    return False

async def remove_bad_word(word: str, guild_id: int, guild_settings: dict) -> bool:
    """Removes a word from the bad_words set for a specific guild, updates cache and Firestore."""
    word = word.lower()
    if word in guild_settings['bad_words']:
        guild_settings['bad_words'].remove(word)
        await _save_guild_settings_to_firestore(guild_id)
        print(f"DEBUG: Removed '{word}' from guild {guild_id}'s bad words. New cache set: {guild_settings['bad_words']}")
        return True
    print(f"DEBUG: '{word}' not found in guild {guild_id}'s bad words.")
    return False

async def get_bad_words(guild_id: int, guild_settings: dict) -> list[str]:
    """Returns a sorted list of all current bad words for a specific guild from cache."""
    cached_words = guild_settings['bad_words']
    print(f"DEBUG: get_bad_words for guild {guild_id} returning from cache: {sorted(list(cached_words))}")
    return sorted(list(cached_words))

# --- Functions for managing exception roles (now accept guild_settings directly) ---

async def add_exception_role(guild_id: int, role_name: str, guild_settings: dict):
    """Adds an exception role for a guild, updates cache and Firestore."""
    if role_name not in guild_settings['exempt_roles']:
        guild_settings['exempt_roles'].add(role_name)
        await _save_guild_settings_to_firestore(guild_id)
        print(f"DEBUG: Added '{role_name}' to guild {guild_id}'s exempt roles. New cache set: {guild_settings['exempt_roles']}")
        return True
    print(f"DEBUG: '{role_name}' already exists in guild {guild_id}'s exempt roles.")
    return False

async def remove_exception_role(guild_id: int, role_name: str, guild_settings: dict):
    """Removes an exception role for a guild, updates cache and Firestore."""
    if role_name in guild_settings['exempt_roles']:
        guild_settings['exempt_roles'].remove(role_name)
        await _save_guild_settings_to_firestore(guild_id)
        print(f"DEBUG: Removed '{role_name}' from guild {guild_id}'s exempt roles. New cache set: {guild_settings['exempt_roles']}")
        return True
    print(f"DEBUG: '{role_name}' not found in guild {guild_id}'s exempt roles.")
    return False

async def is_role_exempt(guild_id: int, role_name: str, guild_settings: dict) -> bool:
    """Checks if a role is exempt for a guild, using provided settings."""
    return role_name in guild_settings['exempt_roles']

async def get_exempt_roles(guild_id: int, guild_settings: dict) -> list[str]:
    """Returns a list of exempt roles for a guild from cache."""
    cached_roles = guild_settings['exempt_roles']
    print(f"DEBUG: get_exempt_roles for guild {guild_id} returning from cache: {sorted(list(cached_roles))}")
    return sorted(list(cached_roles))
