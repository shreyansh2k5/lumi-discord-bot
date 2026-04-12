# services/memory.py
# Per-user conversation memory stored as proper {"role", "content"} message dicts.
# This format feeds directly into the Groq messages[] array.

_memory: dict[str, list[dict]] = {}

MAX_HISTORY = 8  # number of turns (each turn = 1 user + 1 assistant message)


def add_to_memory(user_id: str, role: str, content: str) -> None:
    """Add a single message to memory. role = 'user' or 'assistant'."""
    if user_id not in _memory:
        _memory[user_id] = []
    _memory[user_id].append({"role": role, "content": content})
    # Keep only last MAX_HISTORY * 2 entries (pairs of user + assistant)
    _memory[user_id] = _memory[user_id][-(MAX_HISTORY * 2):]


def get_memory(user_id: str) -> list[dict]:
    """Return conversation history as a messages[] list."""
    return list(_memory.get(user_id, []))


def clear_memory(user_id: str) -> None:
    """Wipe a user's memory."""
    _memory.pop(user_id, None)
