# moderation/automod.py

import re
import unicodedata
from firebase_admin import firestore

_firestore_db_instance = None

# Cache: {guild_id: {'bad_words': set(), 'exempt_roles': set(), 'revive_channels': set(), 'revive_threshold': int}}
_guild_settings_cache: dict = {}


def set_firestore_db(client):
    global _firestore_db_instance
    _firestore_db_instance = client


# ── Firestore helpers ────────────────────────────────────────────

async def _load_guild_settings_from_firestore(guild_id: int):
    if _firestore_db_instance is None:
        return
    try:
        doc = await _firestore_db_instance.collection("guilds").document(str(guild_id)).get()
        settings = {"bad_words": set(), "exempt_roles": set(), "revive_channels": set(), "revive_threshold": 120}
        if doc.exists:
            data = doc.to_dict()
            settings["bad_words"]        = set(data.get("bad_words", []))
            settings["exempt_roles"]     = set(data.get("exempt_roles", []))
            settings["revive_channels"]  = set(int(c) for c in data.get("revive_channels", []))
            settings["revive_threshold"] = int(data.get("revive_threshold", 120))
        _guild_settings_cache[guild_id] = settings
    except Exception as e:
        print(f"[Automod] Error loading settings for guild {guild_id}: {e}")
        _guild_settings_cache[guild_id] = {"bad_words": set(), "exempt_roles": set(), "revive_channels": set(), "revive_threshold": 120}


async def _save_guild_settings_to_firestore(guild_id: int):
    if _firestore_db_instance is None or guild_id not in _guild_settings_cache:
        return
    try:
        await _firestore_db_instance.collection("guilds").document(str(guild_id)).set({
            "bad_words":       list(_guild_settings_cache[guild_id]["bad_words"]),
            "exempt_roles":    list(_guild_settings_cache[guild_id]["exempt_roles"]),
            "revive_channels":  list(_guild_settings_cache[guild_id].get("revive_channels", set())),
            "revive_threshold":  _guild_settings_cache[guild_id].get("revive_threshold", 120),
        }, merge=True)
    except Exception as e:
        print(f"[Automod] Error saving settings for guild {guild_id}: {e}")


async def ensure_guild_settings_in_cache(guild_id: int):
    if guild_id not in _guild_settings_cache:
        await _load_guild_settings_from_firestore(guild_id)


# ── Bad word filter ──────────────────────────────────────────────

_LEET_MAP = str.maketrans({
    "0": "o", "1": "i", "3": "e", "4": "a",
    "5": "s", "6": "g", "7": "t", "8": "b",
    "@": "a", "$": "s",
})


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = text.translate(_LEET_MAP)
    text = re.sub(r"(.)\1{2,}", r"\1", text)
    text = re.sub(r"(?<=[a-z])[^a-z0-9]+(?=[a-z])", "", text)
    return text


def check_bad_words(message: str, guild_id: int, guild_settings: dict) -> bool:
    normalized = _normalize(message)
    return any(
        re.search(r"\b" + re.escape(word) + r"\b", normalized)
        for word in guild_settings["bad_words"]
    )


async def add_bad_word(word: str, guild_id: int, guild_settings: dict) -> bool:
    word = word.lower()
    if word not in guild_settings["bad_words"]:
        guild_settings["bad_words"].add(word)
        await _save_guild_settings_to_firestore(guild_id)
        return True
    return False


async def remove_bad_word(word: str, guild_id: int, guild_settings: dict) -> bool:
    if word.lower() in guild_settings["bad_words"]:
        guild_settings["bad_words"].discard(word.lower())
        await _save_guild_settings_to_firestore(guild_id)
        return True
    return False


async def get_bad_words(guild_id: int, guild_settings: dict) -> list[str]:
    return sorted(guild_settings["bad_words"])


# ── Exempt roles ─────────────────────────────────────────────────

def is_role_exempt(guild_id: int, role_name: str, guild_settings: dict) -> bool:
    return role_name in guild_settings["exempt_roles"]


async def add_exception_role(guild_id: int, role_name: str, guild_settings: dict) -> bool:
    if role_name not in guild_settings["exempt_roles"]:
        guild_settings["exempt_roles"].add(role_name)
        await _save_guild_settings_to_firestore(guild_id)
        return True
    return False


async def remove_exception_role(guild_id: int, role_name: str, guild_settings: dict) -> bool:
    if role_name in guild_settings["exempt_roles"]:
        guild_settings["exempt_roles"].discard(role_name)
        await _save_guild_settings_to_firestore(guild_id)
        return True
    return False


async def get_exempt_roles(guild_id: int, guild_settings: dict) -> list[str]:
    return sorted(guild_settings["exempt_roles"])


# ── Dead-chat revive channels ────────────────────────────────────

async def add_revive_channel(guild_id: int, channel_id: int, guild_settings: dict) -> bool:
    guild_settings.setdefault("revive_channels", set())
    if channel_id not in guild_settings["revive_channels"]:
        guild_settings["revive_channels"].add(channel_id)
        await _save_guild_settings_to_firestore(guild_id)
        return True
    return False


async def remove_revive_channel(guild_id: int, channel_id: int, guild_settings: dict) -> bool:
    if channel_id in guild_settings.get("revive_channels", set()):
        guild_settings["revive_channels"].discard(channel_id)
        await _save_guild_settings_to_firestore(guild_id)
        return True
    return False


def get_revive_channels(guild_id: int, guild_settings: dict) -> list[int]:
    return sorted(guild_settings.get("revive_channels", set()))

# ── Dead-chat revive threshold ───────────────────────────────────

DEFAULT_REVIVE_THRESHOLD_MINUTES = 120  # 2 hours


async def set_revive_threshold(guild_id: int, minutes: int, guild_settings: dict) -> None:
    """Sets how many minutes of silence before Lumi revives chat for this guild."""
    guild_settings["revive_threshold"] = minutes
    await _save_guild_settings_to_firestore(guild_id)


def get_revive_threshold(guild_id: int, guild_settings: dict) -> int:
    """Returns the dead-chat threshold in minutes for this guild (default 120)."""
    return guild_settings.get("revive_threshold", DEFAULT_REVIVE_THRESHOLD_MINUTES)