# bot/client.py
# Owns the bot instance, intents, and the dead-chat revival loop.
# Event handlers live in bot/events.py.

import time
import discord
from discord.ext import commands, tasks

from config import (
    COMMAND_PREFIX,
    DEAD_CHAT_CHECK_INTERVAL_MINUTES,
)
from services.ai import query_groq as query_model
import moderation.automod as automod

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix=COMMAND_PREFIX,
    intents=intents,
    help_command=None,
)

# Tracks the last time any message was sent in any guild
last_message_time = time.time()


@tasks.loop(minutes=DEAD_CHAT_CHECK_INTERVAL_MINUTES)
async def revive_chat_loop():
    """
    Periodically checks whether chat has gone quiet.
    Only sends a revival message to channels whitelisted via /deadchat add.
    Safely skips deleted channels and channels the bot can't write to.
    """
    for guild in bot.guilds:
        try:
            await automod.ensure_guild_settings_in_cache(guild.id)
            guild_settings = automod._guild_settings_cache.get(guild.id, {})

            # Per-guild threshold — skip if chat is still active
            threshold_seconds = automod.get_revive_threshold(guild.id, guild_settings) * 60
            if time.time() - last_message_time <= threshold_seconds:
                continue

            allowed_ids = automod.get_revive_channels(guild.id, guild_settings)

            if not allowed_ids:
                continue

            target_channel = None
            for channel_id in allowed_ids:
                channel = guild.get_channel(channel_id)
                if channel is None:
                    print(f"[DeadChat] Channel {channel_id} in guild {guild.id} no longer exists.")
                    continue
                bot_member = guild.get_member(bot.user.id)
                if not bot_member or not channel.permissions_for(bot_member).send_messages:
                    print(f"[DeadChat] No send permission in #{channel.name} (guild {guild.id}).")
                    continue
                target_channel = channel
                break

            if target_channel is None:
                continue

            emoji_str = " ".join(str(e) for e in guild.emojis[:15])
            prompt = "The chat is dead. Spark a new conversation with something cute!"

            async with target_channel.typing():
                response = await query_model(prompt, server_emojis=emoji_str)
                await target_channel.send(response)

            print(f"[DeadChat] Revived #{target_channel.name} in guild {guild.id}")

        except Exception as e:
            print(f"[DeadChat] Error in guild {guild.id}: {e}")


def get_client() -> commands.Bot:
    return bot