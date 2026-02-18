# bot_config.py

import discord
from discord.ext import commands, tasks # Added tasks
import time # Added time for the dead chat tracker
from groq_api import query_groq as query_model
from personality import apply_personality
from memory_store import get_memory, add_to_memory
import automod
from automod import check_bad_words, is_role_exempt, ensure_guild_settings_in_cache

intents = discord.Intents.default()
intents.message_content = True
intents.members = True # Required to access message.author.roles and new members

bot = commands.Bot(command_prefix="/", intents=intents)

# --- Chat Tracker Variables ---
last_message_time = time.time()
last_active_channel = None


# --- Event Listener for Messages ---
@bot.event
async def on_message(message):
    """
    Handles incoming messages for auto-moderation and mention-based chat.
    """
    await bot.process_commands(message)

    if message.author == bot.user:
        return

    # --- Dead Chat Tracker Update ---
    global last_message_time, last_active_channel
    if message.guild: # Only track server channels, not DMs
        last_message_time = time.time()
        last_active_channel = message.channel

    # If the message is a Direct Message, skip guild-specific logic
    if message.guild is None:
        user_input = message.content.strip()
        user_id = str(message.author.id)

        if bot.user in message.mentions: 
            async with message.channel.typing():
                user_prompt = message.clean_content.replace(f"@{bot.user.name}", "").strip()
                if not user_prompt:
                    user_prompt = "Say something cute!"

                memory = get_memory(user_id)
                final_prompt = f"{memory}\nUser: {user_prompt}"
                prompt = apply_personality(final_prompt)

                response = await query_model(prompt)
                add_to_memory(user_id, f"User: {user_prompt}")
                add_to_memory(user_id, f"Lumi: {response}")

                await message.reply(response) # Added reply here too!
        return 

    # 🚨 Auto-moderation check 
    if isinstance(message.author, discord.Member):
        guild_id = message.guild.id
        
        await ensure_guild_settings_in_cache(guild_id)
        guild_settings = automod._guild_settings_cache.get(guild_id, {'bad_words': set(), 'exempt_roles': set()})

        is_exempt = False
        for role in message.author.roles:
            if is_role_exempt(guild_id, role.name, guild_settings):
                is_exempt = True
                break
        
        if not is_exempt: 
            if check_bad_words(message.content, guild_id, guild_settings):
                await message.delete()
                await message.channel.send(
                    f"⚠️ {message.author.mention}, please avoid using inappropriate language.",
                    delete_after=5
                )
                return 
                
    # ✅ Only extract user info if safe 
    user_input = message.content.strip()
    user_id = str(message.author.id)

    # ✅ If Lumi is mentioned directly 
    if bot.user in message.mentions and not message.reference:
        async with message.channel.typing():
            user_prompt = message.clean_content.replace(f"@{bot.user.name}", "").strip()
            if not user_prompt:
                user_prompt = "Say something cute!"

            memory = get_memory(user_id)
            final_prompt = f"{memory}\nUser: {user_prompt}"
            prompt = apply_personality(final_prompt)

            response = await query_model(prompt)
            add_to_memory(user_id, f"User: {user_prompt}")
            add_to_memory(user_id, f"Lumi: {response}")

            await message.reply(response)

    # ✅ If it's a reply to any message 
    elif message.reference:
        replied_msg = await message.channel.fetch_message(message.reference.message_id)
        
        if replied_msg.author == bot.user:
            async with message.channel.typing():
                memory = get_memory(user_id)
                final_prompt = f"{memory}\nUser: {user_input}"
                prompt = apply_personality(final_prompt)

                response = await query_model(prompt)
                add_to_memory(user_id, f"User: {user_input}")
                add_to_memory(user_id, f"Lumi: {response}")

                await message.reply(response)

# --- Feature: Welcome New Members ---
@bot.event
async def on_member_join(member):
    """Greets new members when they join the server."""
    if member.guild.system_channel:
        await member.guild.system_channel.send(
            f"Yay! Everyone say hi to {member.mention}! 💖 Welcome to the server, I'm Lumi, your AI bestie!"
        )

# --- Feature: Dead Chat Reviver ---
@tasks.loop(minutes=30)
async def revive_chat_loop():
    global last_message_time, last_active_channel
    if last_active_channel is None:
        return
    
    # Check if chat has been dead for 2 hours (7200 seconds)
    # Change to 3600 if you want her to speak after 1 hour!
    if time.time() - last_message_time > 7200:
        async with last_active_channel.typing():
            prompt = apply_personality("The chat has been completely dead and silent for hours. Say something cute, random, or ask a fun question to spark a new conversation!")
            response = await query_model(prompt)
            await last_active_channel.send(response)
            
        last_message_time = time.time() # Reset the timer

def get_client():
    return bot
