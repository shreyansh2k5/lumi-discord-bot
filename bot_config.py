# bot_config.py

import discord
from discord.ext import commands
from groq_api import query_groq as query_model
from personality import apply_personality
from memory_store import get_memory, add_to_memory
from automod import check_bad_words
from role_exceptions import is_role_exempt


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)

@bot.event
async def on_message(message):
    await bot.process_commands(message)

    if message.author == bot.user:
        return

    # 🚨 Auto-moderation check (MUST come early)
    if message.guild:  # only moderate in servers
        guild_id = message.guild.id
        user_roles = [role.name for role in message.author.roles]
        if not any(is_role_exempt(guild_id, role_name) for role_name in user_roles):
            if check_bad_words(message.content):
                await message.delete()
                await message.channel.send(
                    f"⚠️ {message.author.mention}, please avoid using inappropriate language.",
                    delete_after=5
                )
                return
                
    # ✅ Only extract user info if safe
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
