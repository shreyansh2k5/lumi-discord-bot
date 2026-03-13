# bot/events.py

import time
import datetime
import discord
from discord.ext import commands

from bot.client import bot
import moderation.automod as automod
from moderation.automod import check_bad_words, is_role_exempt, ensure_guild_settings_in_cache
from services.ai import query_groq
from services.memory import get_memory, add_to_memory
from config import AI_MAX_INPUT_CHARS

_USAGE_HINTS = {
    "flip":      "🪙 **Usage:** `$flip <amount>`\n**Example:** `$flip 500`",
    "roll":      "🎲 **Usage:** `$roll <amount>`\n**Example:** `$roll 1000`",
    "blackjack": "🃏 **Usage:** `$blackjack <bet>`\n**Example:** `$blackjack 2000`",
    "raid":      "🥷 **Usage:** `$raid <@user>`\n**Example:** `$raid @someone`",
    "give":      "💸 **Usage:** `$give <@user> <amount>`\n**Example:** `$give @someone 500`",
    "balance":   "💰 **Usage:** `$balance` or `$balance <@user>`",
    "profile":   "🌸 **Usage:** `$profile` or `$profile <@user>`",
    "mute":      "🤫 **Usage:** `$mute <@user> <minutes> [reason]`",
    "kick":      "🥾 **Usage:** `$kick <@user> [reason]`",
    "ban":       "🔨 **Usage:** `$ban <@user> [reason]`",
    "shop buy":  "🐾 **Usage:** `$shop buy <pet>`\n**Example:** `$shop buy cat`",
}


def _get_time_of_day() -> str:
    hour = datetime.datetime.now().hour
    if 5  <= hour < 12: return "morning"
    if 12 <= hour < 17: return "afternoon"
    if 17 <= hour < 21: return "evening"
    return "night"


async def _fetch_recent_context(channel: discord.TextChannel, limit: int = 5) -> list[dict]:
    """
    Returns last `limit` non-bot messages as a list of
    {"author_id": ..., "display_name": ..., "content": ...} dicts.
    """
    try:
        msgs = []
        async for msg in channel.history(limit=limit + 2):
            if msg.author.bot:
                continue
            msgs.append({
                "author_id":    msg.author.id,
                "display_name": msg.author.display_name,
                "content":      msg.clean_content[:150],
            })
            if len(msgs) >= limit:
                break
        msgs.reverse()
        return msgs
    except Exception:
        return []


def _build_context_block(recent_msgs: list[dict], current_author_id: int, current_author_name: str) -> str:
    """
    Formats recent chat as a readable block.
    Marks which messages are from the person currently talking to Lumi.
    """
    if not recent_msgs:
        return ""
    lines = []
    for m in recent_msgs:
        tag = " (the person talking to you now)" if m["author_id"] == current_author_id else ""
        lines.append(f"{m['display_name']}{tag}: {m['content']}")
    return "== RECENT CHAT (for awareness only — answer the user's actual question) ==\n" + "\n".join(lines)


@bot.event
async def on_message(message: discord.Message):
    await bot.process_commands(message)

    if message.author == bot.user:
        return

    if message.guild:
        bot.last_message_time = time.time()

    # ── Auto-moderation ──────────────────────────────────────────
    if message.guild and isinstance(message.author, discord.Member):
        guild_id = message.guild.id
        await ensure_guild_settings_in_cache(guild_id)
        guild_settings = automod._guild_settings_cache.get(
            guild_id,
            {"bad_words": set(), "exempt_roles": set(), "revive_channels": set()}
        )
        is_exempt = any(
            is_role_exempt(guild_id, role.name, guild_settings)
            for role in message.author.roles
        )
        if not is_exempt and check_bad_words(message.content, guild_id, guild_settings):
            try:
                await message.delete()
                await message.channel.send(
                    f"⚠️ {message.author.mention}, please avoid using inappropriate language!",
                    delete_after=5
                )
            except discord.Forbidden:
                pass
            return

    # ── Decide if Lumi should respond ───────────────────────────
    is_dm           = message.guild is None
    is_mention      = bot.user in message.mentions and not message.reference
    is_reply_to_bot = False

    if message.reference:
        try:
            replied = await message.channel.fetch_message(message.reference.message_id)
            if replied.author == bot.user:
                is_reply_to_bot = True
        except Exception:
            pass

    if not (is_dm or is_mention or is_reply_to_bot):
        return
    if message.content.startswith("$"):
        return

    # ── @lumi play <query> shortcut ──────────────────────────────
    # Lets users type "@Lumi play never gonna give you up" naturally
    clean_check = message.clean_content.lower()
    for part in [f"@{bot.user.display_name.lower()} play ", f"@{bot.user.name.lower()} play "]:
        if clean_check.startswith(part):
            query = message.clean_content[len(part):].strip()
            if query:
                ctx = await bot.get_context(message)
                await bot.get_cog("Music").play(ctx, query=query)
            return

    # ── Build and send AI response ───────────────────────────────
    async with message.channel.typing():
        user_id      = str(message.author.id)
        # Strip the bot mention from the input so Lumi doesn't repeat it
        clean_input  = message.clean_content
        for mention in message.mentions:
            if mention == bot.user:
                clean_input = clean_input.replace(f"@{mention.display_name}", "").strip()
        clean_input  = clean_input[:AI_MAX_INPUT_CHARS].strip() or "Hi!"

        server_name  = message.guild.name   if message.guild else "DM"
        channel_name = message.channel.name if message.guild else "DM"
        time_of_day  = _get_time_of_day()
        emoji_str    = " ".join(str(e) for e in message.guild.emojis[:20]) if message.guild else ""

        # Fetch recent chat for situational awareness
        recent_msgs  = await _fetch_recent_context(message.channel) if message.guild else []
        context_block = _build_context_block(recent_msgs, message.author.id, message.author.display_name)

        # Who is talking to Lumi right now
        caller_note = (
            f"== WHO IS TALKING TO YOU ==\n"
            f"Name: {message.author.display_name}\n"
            f"Discord mention: <@{message.author.id}>\n"
            f"Address them by name naturally in conversation. "
            f"ONLY use <@{message.author.id}> if you are issuing a moderation warning — NOT in normal replies."
        )

        # Build the final user message: context + caller info + their actual question
        parts = []
        if context_block:
            parts.append(context_block)
        parts.append(caller_note)
        parts.append(f"== THEIR MESSAGE ==\n{clean_input}")
        full_user_content = "\n\n".join(parts)

        # Get conversation history and append new message
        history  = get_memory(user_id)
        messages = history + [{"role": "user", "content": full_user_content}]

        response = await query_groq(
            messages=messages,
            server_emojis=emoji_str,
            server_name=server_name,
            channel_name=channel_name,
            time_of_day=time_of_day,
        )

        # Only store the clean input in memory (not the whole context block)
        add_to_memory(user_id, "user",      clean_input)
        add_to_memory(user_id, "assistant", response)

        await message.reply(response)


@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.MissingRequiredArgument):
        cmd  = ctx.command.qualified_name
        hint = _USAGE_HINTS.get(cmd, "❓ Type `$help` to see how to use this command.")
        return await ctx.send(
            f"⚠️ **Missing:** `{error.param.name}`\n\n{hint}",
            delete_after=15
        )

    if isinstance(error, commands.CommandOnCooldown):
        seconds = int(error.retry_after)
        hours, remainder = divmod(seconds, 3600)
        minutes, secs    = divmod(remainder, 60)
        parts = []
        if hours:   parts.append(f"{hours}h")
        if minutes: parts.append(f"{minutes}m")
        parts.append(f"{secs}s")
        return await ctx.send(
            f"⏳ **Lumi says:** Slow down! Wait `{''.join(parts)}` before using this again!",
            delete_after=10
        )

    if isinstance(error, commands.BadArgument):
        return await ctx.send(
            "❌ **Invalid argument.** Type `$help` to see the correct usage.",
            delete_after=10
        )

    print(f"[CommandError] {error}")


@bot.event
async def on_member_join(member: discord.Member):
    ch = member.guild.system_channel
    if ch and ch.permissions_for(member.guild.me).send_messages:
        await ch.send(
            f"Yay! Everyone say hi to {member.mention}! 💖 "
            f"Welcome to **{member.guild.name}** — I'm Lumi, your AI bestie! Type `$help` to see what I can do~ ✨"
        )
