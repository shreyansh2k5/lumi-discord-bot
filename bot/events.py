# bot/events.py
# All discord.py event listeners.
# Registered on the bot instance imported from bot/client.py.

import discord
from discord.ext import commands

from bot.client import bot, last_message_time
import moderation.automod as automod
from moderation.automod import check_bad_words, is_role_exempt, ensure_guild_settings_in_cache
from services.ai import query_groq as query_model
from services.memory import get_memory, add_to_memory
from config import AI_MAX_INPUT_CHARS

import time

# Usage hints shown when a required argument is missing
_USAGE_HINTS = {
    "flip":      "🪙 **Usage:** `$flip <amount>`\n**Example:** `$flip 500`",
    "roll":      "🎲 **Usage:** `$roll <amount>`\n**Example:** `$roll 1000`",
    "blackjack": "🃏 **Usage:** `$blackjack <bet>`\n**Example:** `$blackjack 2000`",
    "raid":      "🥷 **Usage:** `$raid <@user>`\n**Example:** `$raid @someone`",
    "give":      "💸 **Usage:** `$give <@user> <amount>`\n**Example:** `$give @someone 500`",
    "balance":   "💰 **Usage:** `$balance` or `$balance <@user>`",
    "profile":   "🌸 **Usage:** `$profile` or `$profile <@user>`",
    "mute":      "🤫 **Usage:** `$mute <@user> <minutes> [reason]`\n**Example:** `$mute @someone 10 spamming`",
    "kick":      "🥾 **Usage:** `$kick <@user> [reason]`\n**Example:** `$kick @someone rule breaking`",
    "ban":       "🔨 **Usage:** `$ban <@user> [reason]`\n**Example:** `$ban @someone harassment`",
    "shop buy":  "🐾 **Usage:** `$shop buy <pet>`\n**Example:** `$shop buy cat`",
}


@bot.event
async def on_message(message: discord.Message):
    # 1. Let prefix / hybrid commands ($) run first
    await bot.process_commands(message)

    # 2. Ignore the bot's own messages
    if message.author == bot.user:
        return

    # 3. Update dead-chat timer
    global last_message_time
    if message.guild:
        last_message_time = time.time()

    # 4. Auto-moderation
    if message.guild and isinstance(message.author, discord.Member):
        guild_id = message.guild.id
        await ensure_guild_settings_in_cache(guild_id)
        guild_settings = automod._guild_settings_cache.get(
            guild_id,
            {'bad_words': set(), 'exempt_roles': set(), 'revive_channels': set()}
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

    # 5. AI response (DM, @mention, or reply to bot)
    is_dm = message.guild is None
    is_mention = bot.user in message.mentions and not message.reference
    is_reply_to_bot = False

    if message.reference:
        try:
            replied = await message.channel.fetch_message(message.reference.message_id)
            if replied.author == bot.user:
                is_reply_to_bot = True
        except Exception:
            pass

    if (is_dm or is_mention or is_reply_to_bot) and not message.content.startswith("$"):
        async with message.channel.typing():
            user_id = str(message.author.id)
            clean_input = message.clean_content.replace(f"@{bot.user.name}", "").strip()
            clean_input = clean_input[:AI_MAX_INPUT_CHARS] or "Say something cute!"

            emoji_str = ""
            if message.guild:
                emoji_str = " ".join(str(e) for e in message.guild.emojis[:20])

            memory = get_memory(user_id)
            context_input = f"{memory}\nUser: {clean_input}"

            response = await query_model(context_input, server_emojis=emoji_str)
            add_to_memory(user_id, f"User: {clean_input}")
            add_to_memory(user_id, f"Lumi: {response}")
            await message.reply(response)


@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.MissingRequiredArgument):
        cmd  = ctx.command.qualified_name  # e.g. "shop buy" for subcommands
        hint = _USAGE_HINTS.get(cmd, f"❓ Type `$help` to see how to use this command.")
        return await ctx.send(
            f"⚠️ **Missing:** `{error.param.name}`\n\n{hint}",
            delete_after=15
        )

    if isinstance(error, commands.CommandOnCooldown):
        seconds = int(error.retry_after)
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)

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
            f"❌ **Invalid argument.** Type `$help` to see the correct usage.",
            delete_after=10
        )

    print(f"[CommandError] {error}")


@bot.event
async def on_member_join(member: discord.Member):
    if member.guild.system_channel:
        await member.guild.system_channel.send(
            f"Yay! Everyone say hi to {member.mention}! 💖 "
            f"Welcome to the server — I'm Lumi, your AI bestie!"
        )