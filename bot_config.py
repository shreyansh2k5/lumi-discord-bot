# bot_config.py

import discord
from discord.ext import commands, tasks
import time
from groq_api import query_groq as query_model
# REMOVED: apply_personality (Personality is now handled via System Prompt in groq_api)
import automod
from automod import check_bad_words, is_role_exempt, ensure_guild_settings_in_cache
from memory_store import get_memory, add_to_memory

intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

bot = commands.Bot(command_prefix="/", intents=intents)

# --- Chat Tracker Variables ---
last_message_time = time.time()
last_active_channel = None

@bot.event
async def on_message(message):
    """
    Handles incoming messages for auto-moderation and AI interaction.
    """
    # 1. Allow commands to run
    await bot.process_commands(message)

    # 2. Ignore the bot's own messages
    if message.author == bot.user:
        return

    # 3. Dead Chat Tracker Update
    global last_message_time, last_active_channel
    if message.guild:
        last_message_time = time.time()
        last_active_channel = message.channel

    # 4. 🚨 Auto-moderation check (only in guilds)
    if message.guild and isinstance(message.author, discord.Member):
        guild_id = message.guild.id
        await ensure_guild_settings_in_cache(guild_id)
        guild_settings = automod._guild_settings_cache.get(guild_id, {'bad_words': set(), 'exempt_roles': set()})

        # Check if user has an exempt role
        is_exempt = False
        for role in message.author.roles:
            if is_role_exempt(guild_id, role.name, guild_settings):
                is_exempt = True
                break
        
        if not is_exempt: 
            if check_bad_words(message.content, guild_id, guild_settings):
                try:
                    await message.delete()
                    await message.channel.send(
                        f"⚠️ {message.author.mention}, please avoid using inappropriate language!",
                        delete_after=5
                    )
                except discord.Forbidden:
                    print(f"Missing permissions to delete message in {message.guild.name}")
                return 

    # 5. ✨ AI Response Logic (Mentions, Replies, or DMs)
    is_dm = message.guild is None
    is_mention = bot.user in message.mentions and not message.reference
    is_reply_to_bot = False
    
    if message.reference:
        try:
            replied_msg = await message.channel.fetch_message(message.reference.message_id)
            if replied_msg.author == bot.user:
                is_reply_to_bot = True
        except:
            pass

    if is_dm or is_mention or is_reply_to_bot:
        async with message.channel.typing():
            user_id = str(message.author.id)
            
            # Clean up the input (remove the bot mention)
            clean_input = message.clean_content.replace(f"@{bot.user.name}", "").strip()
            if not clean_input:
                clean_input = "Say something cute!"

            # 🛠️ EMOJI VISION: Fetch server emojis to pass to the AI
            emoji_str = ""
            if message.guild:
                # Get the first 20 custom emojis in string format
                emoji_str = " ".join([str(e) for e in message.guild.emojis[:20]])

            # Get Conversation Memory
            memory = get_memory(user_id)
            context_input = f"{memory}\nUser: {clean_input}"

            # Query the model (groq_api handles the personality/system prompt)
            response = await query_model(context_input, server_emojis=emoji_str)

            # Update Memory
            add_to_memory(user_id, f"User: {clean_input}")
            add_to_memory(user_id, f"Lumi: {response}")

            # Send response
            await message.reply(response)

# --- Feature: Welcome New Members ---
@bot.event
async def on_member_join(member):
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
    if time.time() - last_message_time > 7200:
        async with last_active_channel.typing():
            # Let Lumi see the emojis even when reviving chat
            emoji_str = ""
            if last_active_channel.guild:
                emoji_str = " ".join([str(e) for e in last_active_channel.guild.emojis[:15]])
            
            prompt = "The chat is dead. Spark a new conversation with something cute or a fun question!"
            response = await query_model(prompt, server_emojis=emoji_str)
            await last_active_channel.send(response)
            
        last_message_time = time.time() 

def get_client():
    return bot
