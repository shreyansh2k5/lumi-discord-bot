# bot_config.py

import discord
from groq_api import query_groq as query_model
from personality import apply_personality
from memory_store import get_memory, add_to_memory

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    user_input = message.content.strip()
    user_id = str(message.author.id)

    # ✅ Mentioned Lumi directly (not a reply)
    if client.user in message.mentions and not message.reference:
        user_prompt = message.clean_content.replace(f"@{client.user.name}", "").strip()
        if not user_prompt:
            user_prompt = "Say something cute!"

        # Include memory
        memory = get_memory(user_id)
        final_prompt = f"{memory}\nUser: {user_prompt}"
        prompt = apply_personality(final_prompt)

        response = await query_model(prompt)
        add_to_memory(user_id, f"User: {user_prompt}")
        add_to_memory(user_id, f"Lumi: {response}")

        await message.channel.send(response)

    # ✅ Replied to Lumi
    elif message.reference:
        replied_msg = await message.channel.fetch_message(message.reference.message_id)
        if replied_msg.author == client.user:
            memory = get_memory(user_id)
            final_prompt = f"{memory}\nUser: {user_input}"
            prompt = apply_personality(final_prompt)

            response = await query_model(prompt)
            add_to_memory(user_id, f"User: {user_input}")
            add_to_memory(user_id, f"Lumi: {response}")

            await message.channel.send(response)

def get_client():
    return client
