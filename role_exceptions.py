# role_exceptions.py

# In-memory store (you can replace with database later)
role_exceptions = {}

def add_exception_role(guild_id: int, role_name: str):
    if guild_id not in role_exceptions:
        role_exceptions[guild_id] = set()
    role_exceptions[guild_id].add(role_name)

def remove_exception_role(guild_id: int, role_name: str):
    if guild_id in role_exceptions and role_name in role_exceptions[guild_id]:
        role_exceptions[guild_id].remove(role_name)

def is_role_exempt(guild_id: int, role_name: str) -> bool:
    return role_name in role_exceptions.get(guild_id, set())

def get_exempt_roles(guild_id: int) -> list:
    return list(role_exceptions.get(guild_id, []))
