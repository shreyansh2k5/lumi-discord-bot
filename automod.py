# automod.py

# List of bad words (lowercase). You can expand this list.
banned_words = {
    "idiot", "stupid", "dumb", "shit", "fuck", "bitch", "asshole", "kill", "moron"
}

def check_bad_words(message: str) -> bool:
    """Returns True if the message contains any banned words."""
    content = message.lower()
    return any(bad_word in content for bad_word in banned_words)
