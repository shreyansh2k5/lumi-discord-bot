# bot_config.py

import discord
from groq_api import query_groq as query_model
from personality import apply_personality
from memory_store import add_to_memory, get_memory  # ✅ NEW

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    user_input = message.content.strip()
    user_id = str(message.author.id)  # ✅ NEW

    # ✅ Store user's message in memory
    add_to_memory(user_id, f"User: {user_input}")

    # ✅ Get memory history and append current user message
    history = "\n".join(get_memory(user_id))
    full_prompt = f"{history}\nUser: {user_input}"
    prompt = apply_personality(full_prompt)

    # ✅ Make sure only one block is triggered
    # Case 1: Mentioned Lumi
    if client.user in message.mentions and not message.reference:
        response = await query_model(prompt)
        await message.channel.send(response)

    # Case 2: Replied to Lumi
    elif message.reference:
        replied_msg = await message.channel.fetch_message(message.reference.message_id)
        if replied_msg.author == client.user:
            response = await query_model(prompt)
            await message.channel.send(response)

    # ✅ Save Lumi's reply in memory
    add_to_memory(user_id, f"Lumi: {response}")

def get_client():
    return client
