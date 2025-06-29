# automod.py

# List of banned words (you can expand this)
banned_words = {
     "bitch", "asshole", "kill", "moron", "slut", "madarchod", "randi", "rape", "cp"
}

def check_bad_words(message: str) -> bool:
    """
    Checks if the given message contains any banned words.
    Returns True if any are found, else False.
    """
    content = message.lower()
    return any(bad_word in content for bad_word in banned_words)
