import discord
from discord.ext import commands
from groq_api import query_groq as query_model
from personality import apply_personality
from memory_store import get_memory, add_to_memory
from slash_commands import setup_slash_commands  # ✅ async function

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    await setup_slash_commands(bot)  # ✅ FIXED: await this async function
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user} and slash commands synced.")

@bot.event
async def on_message(message):
    await bot.process_commands(message)

    if message.author == bot.user:
        return

    user_input = message.content.strip()
    user_id = str(message.author.id)

    # ✅ Mentioned Lumi directly
    if bot.user in message.mentions and not message.reference:
        user_prompt = message.clean_content.replace(f"@{bot.user.name}", "").strip()
        if not user_prompt:
            user_prompt = "Say something cute!"

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
        if replied_msg.author == bot.user:
            memory = get_memory(user_id)
            final_prompt = f"{memory}\nUser: {user_input}"
            prompt = apply_personality(final_prompt)

            response = await query_model(prompt)
            add_to_memory(user_id, f"User: {user_input}")
            add_to_memory(user_id, f"Lumi: {response}")

            await message.channel.send(response)

def get_client():
    return bot
