# automod.py

banned_words = {"randi", "madarchod", "rape", "cp"}  # Customize these

user_offenses = {}

MAX_OFFENSES = 3  # After this, we timeout the user (optional)

def check_bad_words(message: str) -> bool:
    return any(bad_word in message.lower() for bad_word in banned_words)

def register_offense(user_id: int):
    if user_id not in user_offenses:
        user_offenses[user_id] = 1
    else:
        user_offenses[user_id] += 1
    return user_offenses[user_id]
