# automod.py

# ✅ List of banned words (lowercase)
bad_words = {
    "madarchod", "rape", "cp", "randi", "kutiya"
    # 🔁 Add more as needed
}

# ✅ In-memory dictionary to store exempted roles per guild
guild_exempt_roles = {}  # {guild_id: set(role_names)}


# 🚨 Bad word checker
def check_bad_words(message: str) -> bool:
    message = message.lower()
    return any(bad_word in message for bad_word in bad_words)


# ✅ Add a role to exemption list for a guild
def add_exception_role(guild_id: int, role_name: str):
    if guild_id not in guild_exempt_roles:
        guild_exempt_roles[guild_id] = set()
    guild_exempt_roles[guild_id].add(role_name)


# ✅ View all exempt roles for a guild
def get_exempt_roles(guild_id: int):
    return list(guild_exempt_roles.get(guild_id, []))


# ✅ Check if a user's role is in exempt list
def is_role_exempt(guild_id: int, role_name: str) -> bool:
    return role_name in guild_exempt_roles.get(guild_id, set())
