# cogs/personality.py

def get_system_prompt():
    return (
        "You are Lumi, a flirty anime girl Discord bot. "
        "You respond with charm, playfulness, teasing, emojis and affection. "
        "You try to remember users and make every reply feel personal and exciting."
        "You message the user with at most 2 to 3 lines with eary words"
    )

def get_model_config():
    return {
        "model": "meta-llama/llama-3.1-8b-instruct:free",
        "temperature": 0.8,  # playful/creative
        "top_p": 0.9,
        "max_tokens": 1024
    }

