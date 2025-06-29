# Role exceptions per guild
role_exceptions = {}

def is_role_exempt(guild_id: int, role_name: str) -> bool:
    return role_name in role_exceptions.get(guild_id, set())

def add_role_exception(guild_id: int, role_name: str):
    if guild_id not in role_exceptions:
        role_exceptions[guild_id] = set()
    role_exceptions[guild_id].add(role_name)
