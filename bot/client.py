# bot/client.py
# Owns the bot instance, intents, and the dead-chat revival loop.
# Event handlers live in bot/events.py.

import time
import discord
from discord.ext import commands, tasks

from config import COMMAND_PREFIX
from services.ai import query_groq as query_model
import moderation.automod as automod

# Per-channel last-message timestamp: {channel_id: float}
# Stored here so events.py can import and update it.
channel_last_message: dict[int, float] = {}

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix=COMMAND_PREFIX,
    intents=intents,
    help_command=None,
)



@tasks.loop(minutes=5)
async def revive_chat_loop():
    """
    Periodically checks whether chat has gone quiet in each whitelisted channel.
    Uses per-channel timestamps so guilds don't interfere with each other.
    Only sends a revival message if the channel has been silent for the configured threshold.
    """
    now = time.time()

    for guild in bot.guilds:
        try:
            await automod.ensure_guild_settings_in_cache(guild.id)
            guild_settings = automod._guild_settings_cache.get(guild.id, {})

            allowed_ids = automod.get_revive_channels(guild.id, guild_settings)
            if not allowed_ids:
                continue

            # Per-guild silence threshold in seconds
            threshold_seconds = automod.get_revive_threshold(guild.id, guild_settings) * 60

            for channel_id in allowed_ids:
                channel = guild.get_channel(channel_id)
                if channel is None:
                    print(f"[DeadChat] Channel {channel_id} in guild {guild.id} no longer exists.")
                    continue

                bot_member = guild.get_member(bot.user.id)
                if not bot_member or not channel.permissions_for(bot_member).send_messages:
                    print(f"[DeadChat] No send permission in #{channel.name} (guild {guild.id}).")
                    continue

                # Use per-channel timestamp; default to epoch so a brand-new channel
                # doesn't fire immediately — it'll fire after the first threshold period.
                last_seen = channel_last_message.get(channel_id)
                if last_seen is None:
                    # We haven't observed this channel yet — seed it from Discord history
                    try:
                        async for msg in channel.history(limit=1):
                            last_seen = msg.created_at.timestamp()
                            break
                    except Exception:
                        pass
                    # If still None (empty channel or no access), seed with now so we
                    # don't immediately spam a brand-new / just-configured channel.
                    channel_last_message[channel_id] = last_seen if last_seen is not None else now
                    last_seen = channel_last_message[channel_id]

                elapsed = now - last_seen
                if elapsed <= threshold_seconds:
                    continue  # Chat is still alive in this channel

                # --- Chat is dead — send a revival message ---
                emoji_str = ", ".join(f"{e.name}: {str(e)}" for e in guild.emojis[:15])
                messages = [{"role": "user", "content": "The chat has been dead for a while. Start a fun, cute conversation to get people talking again!"}]

                async with channel.typing():
                    response = await query_model(
                        messages=messages,
                        server_emojis=emoji_str,
                        server_name=guild.name,
                    )
                    await channel.send(response)

                # IMPORTANT: update the timestamp so we don't fire again next tick
                channel_last_message[channel_id] = now
                print(f"[DeadChat] Revived #{channel.name} in guild {guild.id} (silent for {elapsed/60:.1f}m)")

        except Exception as e:
            print(f"[DeadChat] Error in guild {guild.id}: {e}")


def get_client() -> commands.Bot:
    return bot
