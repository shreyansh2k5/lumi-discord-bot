# memory_store.py

# In-memory short-term memory storage (cleared on restart)
memory = {}  # Maps str(user_id) to list of past messages

def add_to_memory(user_id: str, message: str, max_messages: int = 10) -> None:
    """Add a message to the user's memory, keeping only the last max_messages."""
    if user_id not in memory:
        memory[user_id] = []
    memory[user_id].append(message)
    memory[user_id] = memory[user_id][-max_messages:]

def get_memory(user_id: str) -> list[str]:
    """Retrieve recent messages for a given user_id."""
    return memory.get(user_id, [])

