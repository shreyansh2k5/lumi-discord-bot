# services/memory.py
# Short-term per-user conversation memory (in-process, cleared on restart).
# To make memory persistent across restarts, swap this dict for Firestore reads/writes.

_memory: dict[str, list[str]] = {}


def add_to_memory(user_id: str, message: str, max_messages: int = 10) -> None:
    """Add a message to the user's memory, keeping only the last max_messages entries."""
    if user_id not in _memory:
        _memory[user_id] = []
    _memory[user_id].append(message)
    _memory[user_id] = _memory[user_id][-max_messages:]


def get_memory(user_id: str) -> list[str]:
    """Retrieve recent messages for a given user."""
    return _memory.get(user_id, [])


def clear_memory(user_id: str) -> None:
    """Wipe a user's memory (useful for testing or admin resets)."""
    _memory.pop(user_id, None)
