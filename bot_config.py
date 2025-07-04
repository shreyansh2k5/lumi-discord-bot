# bot_config.py

import discord
from discord.ext import commands
from groq_api import query_groq as query_model
from personality import apply_personality
from memory_store import get_memory, add_to_memory
# Import the automod module itself
import automod
# Import specific functions from automod (these are called without 'automod.')
from automod import check_bad_words, is_role_exempt, ensure_guild_settings_in_cache


intents = discord.Intents.default()
intents.message_content = True
intents.members = True # Required to access message.author.roles in guild messages

bot = commands.Bot(command_prefix="/", intents=intents)

# --- Removed: Event Listener for Button Interactions (for moderation confirmation) ---


# --- Event Listener for Messages ---
@bot.event
async def on_message(message):
    """
    Handles incoming messages for auto-moderation and mention-based chat.
    """
    # Always process traditional commands first (if any are defined)
    await bot.process_commands(message)

    if message.author == bot.user:
        return

    # 🚨 Auto-moderation check (MUST come early)
    if message.guild:  # only moderate in servers
        guild_id = message.guild.id
        
        # CRITICAL OPTIMIZATION: Load guild settings into cache ONCE per message event
        await ensure_guild_settings_in_cache(guild_id)
        # Get the cached settings for this guild
        guild_settings = automod._guild_settings_cache.get(guild_id, {'bad_words': set(), 'exempt_roles': set()})

        is_exempt = False
        for role in message.author.roles:
            # CRITICAL FIX: No await here, as is_role_exempt is now synchronous
            if is_role_exempt(guild_id, role.name, guild_settings):
                is_exempt = True
                break
        
        if not is_exempt: # Check if the user is NOT exempt
            # CRITICAL FIX: No await here, as check_bad_words is now synchronous
            if check_bad_words(message.content, guild_id, guild_settings):
                await message.delete()
                await message.channel.send(
                    f"⚠️ {message.author.mention}, please avoid using inappropriate language.",
                    delete_after=5
                )
                return # Stop processing if a bad word is detected
                
    # ✅ Only extract user info if safe
    user_input = message.content.strip()
    user_id = str(message.author.id)

    # ✅ If Lumi is mentioned directly (and not a reply with moderation intent)
    if bot.user in message.mentions and not message.reference:
        # CRITICAL FIX: Trigger typing indicator immediately
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

            await message.channel.send(response)

    # ✅ If it's a reply to any message (check for moderation intent or reply to Lumi)
    elif message.reference:
        replied_msg = await message.channel.fetch_message(message.reference.message_id)
        
        # This block now only contains the original AI chat logic if it's a reply to Lumi.
        if replied_msg.author == bot.user:
            # CRITICAL FIX: Trigger typing indicator immediately
            async with message.channel.typing():
                memory = get_memory(user_id)
                final_prompt = f"{memory}\nUser: {user_input}"
                prompt = apply_personality(final_prompt)

                response = await query_model(prompt)
                add_to_memory(user_id, f"User: {user_input}")
                add_to_memory(user_id, f"Lumi: {response}")

                await message.channel.send(response)

def get_client():
    return bot
