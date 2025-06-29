# automod.py

# List of banned words (you can expand this)
banned_words = {
    "idiot", "stupid", "dumb", "shit", "fuck", "bitch", "asshole", "kill", "moron",
    "retard", "slut", "bastard", "crap", "faggot"
}

def check_bad_words(message: str) -> bool:
    """
    Checks if the given message contains any banned words.
    Returns True if any are found, else False.
    """
    content = message.lower()
    return any(bad_word in content for bad_word in banned_words)
