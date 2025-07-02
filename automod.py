# automod.py

import json
import os

# Define the path for the data file where exceptions will be stored
DATA_FILE = 'exempt_roles.json'

# ✅ List of banned words (lowercase) - Note: This list is still in-memory.
# If you want it to persist, similar save/load logic would be needed.
bad_words = {
    "madarchod", "rape", "cp", "randi", "kutiya"
    # 🔁 Add more as needed
}

# ✅ Dictionary to store exempted roles per guild
# This will now be loaded from/saved to a file for persistence
guild_exempt_roles = {}


# --- Persistence functions for guild_exempt_roles ---

def _load_exceptions():
    """Loads exempted roles from the DATA_FILE."""
    global guild_exempt_roles
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                loaded_data = json.load(f)
                # Convert list of roles (from JSON) back to set for each guild
                # Ensure guild_id is an int key
                guild_exempt_roles = {int(guild_id): set(roles) for guild_id, roles in loaded_data.items()}
            print(f"Loaded exception roles from {DATA_FILE}")
        except json.JSONDecodeError:
            print(f"Error decoding JSON from {DATA_FILE}. Starting with empty exceptions.")
            guild_exempt_roles = {}
        except Exception as e:
            print(f"An unexpected error occurred loading exceptions: {e}")
            guild_exempt_roles = {}
    else:
        print(f"{DATA_FILE} not found. Starting with empty exception roles.")
        guild_exempt_roles = {}

def _save_exceptions():
    """Saves current exempted roles to the DATA_FILE."""
    # Convert sets to lists for JSON serialization (JSON doesn't support sets directly)
    data_to_save = {str(guild_id): list(roles) for guild_id, roles in guild_exempt_roles.items()}
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data_to_save, f, indent=4) # Use indent for readability
        print(f"Saved exception roles to {DATA_FILE}")
    except Exception as e:
        print(f"Error saving exception roles to {DATA_FILE}: {e}")

# Load exceptions when the module is imported (i.e., when the bot starts)
_load_exceptions()

# 🚨 Bad word checker
def check_bad_words(message: str) -> bool:
    message = message.lower()
    return any(bad_word in message for bad_word in bad_words)


# ✅ Add a role to exemption list for a guild
def add_exception_role(guild_id: int, role_name: str):
    if guild_id not in guild_exempt_roles:
        guild_exempt_roles[guild_id] = set()
    guild_exempt_roles[guild_id].add(role_name)
    _save_exceptions() # Save after modification


# ✅ Remove a role from the exemption list for a guild
def remove_exception_role(guild_id: int, role_name: str):
    if guild_id in guild_exempt_roles:
        guild_exempt_roles[guild_id].discard(role_name)
        _save_exceptions() # Save after modification


# ✅ View all exempt roles for a guild
def get_exempt_roles(guild_id: int):
    return list(guild_exempt_roles.get(guild_id, []))


# ✅ Check if a user's role is in exempt list
def is_role_exempt(guild_id: int, role_name: str) -> bool:
    return role_name in guild_exempt_roles.get(guild_id, set())


# --- Functions for managing bad words (added in previous turn, still in-memory) ---
def add_bad_word(word: str) -> bool:
    """Adds a word to the global bad_words set."""
    word = word.lower()
    if word not in bad_words:
        bad_words.add(word)
        return True
    return False

def remove_bad_word(word: str) -> bool:
    """Removes a word from the global bad_words set."""
    word = word.lower()
    if word in bad_words:
        bad_words.remove(word)
        return True
    return False

def get_bad_words() -> list[str]:
    """Returns a sorted list of all current bad words."""
    return sorted(list(bad_words))
