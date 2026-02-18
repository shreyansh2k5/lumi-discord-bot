import random
import discord
from discord import app_commands
from discord.app_commands import checks, Choice
from datetime import timedelta
import automod
from automod import (
    add_exception_role, get_exempt_roles, remove_exception_role,
    add_bad_word, remove_bad_word, get_bad_words,
    ensure_guild_settings_in_cache
)

async def setup_slash_commands(bot: discord.Client):
    @app_commands.command(name="roll", description="Roll a dice 🎲")
    async def roll(interaction: discord.Interaction):
        await interaction.response.defer()
        result = random.randint(1, 6)
        await interaction.followup.send(f"🎲 You rolled a **{result}**!")

    @app_commands.command(name="flip", description="Flip a coin 🪙")
    async def flip(interaction: discord.Interaction):
        await interaction.response.defer()
        result = random.choice(["Heads", "Tails"])
        await interaction.followup.send(f"🪙 You got **{result}**!")

    @app_commands.command(name="status", description="Check Lumi's status 📊")
    async def status(interaction: discord.Interaction):
        await interaction.response.defer()
        latency = round(bot.latency * 1000)
        await interaction.followup.send(
            f"🛰️ Online as **{bot.user.name}**\n"
            f"📡 Latency: `{latency}ms`\n"
            f"🧠 Model: LLaMA-3 (via Groq API)"
        )

    # --- MODERATION COMMANDS (PUBLIC MESSAGES) ---

    @app_commands.command(name="mute", description="Mute (timeout) a user 🤫")
    @checks.has_permissions(moderate_members=True)
    @app_commands.describe(member="The user to mute", duration="Duration in minutes", reason="Reason for muting")
    async def mute(interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = None):
        await interaction.response.defer()
        
        dm_message = f"You have been muted in **{interaction.guild.name}** for {duration} minutes."
        if reason: dm_message += f"\n**Reason:** {reason}"
        try:
            await member.send(dm_message)
        except discord.Forbidden:
            pass 

        try:
            time_delta = timedelta(minutes=duration)
            await member.timeout(time_delta, reason=reason)
            await interaction.followup.send(f"✅ Successfully muted {member.mention} for {duration} minutes.")
        except discord.Forbidden:
            await interaction.followup.send(f"⚠️ I cannot mute {member.mention}. My role might be lower than theirs!")

    @app_commands.command(name="kick", description="Kick a user from the server 🥾")
    @checks.has_permissions(kick_members=True)
    @app_commands.describe(member="The user to kick", reason="Reason for kicking")
    async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = None):
        await interaction.response.defer()

        dm_message = f"You have been kicked from **{interaction.guild.name}**."
        if reason: dm_message += f"\n**Reason:** {reason}"
        try:
            await member.send(dm_message)
        except discord.Forbidden:
            pass

        try:
            await member.kick(reason=reason)
            await interaction.followup.send(f"✅ Successfully kicked **{member.name}**.")
        except discord.Forbidden:
            await interaction.followup.send(f"⚠️ I cannot kick {member.mention}. My role might be lower than theirs!")

    @app_commands.command(name="ban", description="Ban a user from the server 🔨")
    @checks.has_permissions(ban_members=True)
    @app_commands.describe(member="The user to ban", delete_messages="Time period of messages to delete", reason="Reason for banning")
    @app_commands.choices(delete_messages=[
        Choice(name="Don't delete any", value=0),
        Choice(name="Last 10 minutes", value=600),
        Choice(name="Last 30 minutes", value=1800),
        Choice(name="Last 1 hour", value=3600),
        Choice(name="Last 24 hours", value=86400)
    ])
    async def ban(interaction: discord.Interaction, member: discord.Member, delete_messages: Choice[int], reason: str = None):
        await interaction.response.defer()

        dm_message = f"You have been banned from **{interaction.guild.name}**."
        if reason: dm_message += f"\n**Reason:** {reason}"
        try:
            await member.send(dm_message)
        except discord.Forbidden:
            pass

        try:
            await member.ban(reason=reason, delete_message_seconds=delete_messages.value)
            await interaction.followup.send(f"✅ Successfully banned **{member.name}**.")
        except discord.Forbidden:
            await interaction.followup.send(f"⚠️ I cannot ban {member.mention}. My role might be lower than theirs!")

    @app_commands.command(name="softban", description="Softban a user (Kicks them AND deletes their recent messages) 🧹")
    @checks.has_permissions(ban_members=True)
    @app_commands.describe(member="The user to softban", delete_messages="Time period of messages to delete", reason="Reason for softbanning")
    @app_commands.choices(delete_messages=[
        Choice(name="Last 10 minutes", value=600),
        Choice(name="Last 30 minutes", value=1800),
        Choice(name="Last 1 hour", value=3600),
        Choice(name="Last 24 hours", value=86400)
    ])
    async def softban(interaction: discord.Interaction, member: discord.Member, delete_messages: Choice[int], reason: str = None):
        await interaction.response.defer()

        # 1. DM the user (tell them they were kicked, since they aren't permanently banned)
        dm_message = f"You have been kicked from **{interaction.guild.name}** and your recent messages were deleted."
        if reason: dm_message += f"\n**Reason:** {reason}"
        try:
            await member.send(dm_message)
        except discord.Forbidden:
            pass

        # 2. Ban and instantly Unban the user
        try:
            # Step A: Ban them (this deletes the messages)
            await member.ban(reason=reason, delete_message_seconds=delete_messages.value)
            
            # Step B: Instantly unban them (so they can use invite links to come back)
            await interaction.guild.unban(member, reason="Softban complete (auto-unban)")
            
            await interaction.followup.send(f"🧹 Successfully softbanned **{member.name}** (Kicked and messages deleted).")
        except discord.Forbidden:
            await interaction.followup.send(f"⚠️ I cannot softban {member.mention}. My role might be lower than theirs!")


    # --- EXISTING AUTO-MOD COMMANDS ---

    @app_commands.command(name="add_exception_role", description="Exclude a role from auto-moderation")
    @checks.has_permissions(manage_guild=True)
    async def add_exception(interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        await ensure_guild_settings_in_cache(interaction.guild_id)
        guild_settings = automod._guild_settings_cache.get(interaction.guild_id)
        if await add_exception_role(interaction.guild_id, role.name, guild_settings):
            await interaction.followup.send(f"✅ `{role.name}` will now be excluded from moderation.", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ `{role.name}` is already an exempted role.", ephemeral=True)

    @app_commands.command(name="remove_exception_role", description="Remove a role from exception list")
    @checks.has_permissions(manage_guild=True)
    async def remove_exception(interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        await ensure_guild_settings_in_cache(interaction.guild_id)
        guild_settings = automod._guild_settings_cache.get(interaction.guild_id)
        if await remove_exception_role(interaction.guild_id, role.name, guild_settings):
            await interaction.followup.send(f"🗑️ `{role.name}` removed from exception list.", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ `{role.name}` was not found in the exception list.", ephemeral=True)

    @app_commands.command(name="view_exceptions", description="View excluded roles from moderation")
    @checks.has_permissions(manage_guild=True)
    async def view_exceptions(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await ensure_guild_settings_in_cache(interaction.guild_id)
        guild_settings = automod._guild_settings_cache.get(interaction.guild_id)
        roles = await get_exempt_roles(interaction.guild_id, guild_settings)
        if roles:
            await interaction.followup.send(f"🚫 Exempted roles: {', '.join(roles)}", ephemeral=True)
        else:
            await interaction.followup.send("✅ No roles are currently exempted.", ephemeral=True)

    badword_group = app_commands.Group(name="badword", description="Manage auto-moderated words. 🚫")

    @badword_group.command(name="add", description="Add a word to the auto-moderation list.")
    @checks.has_permissions(manage_guild=True)
    async def badword_add(interaction: discord.Interaction, word: str):
        await interaction.response.defer(ephemeral=True)
        await ensure_guild_settings_in_cache(interaction.guild_id)
        guild_settings = automod._guild_settings_cache.get(interaction.guild_id)
        if await add_bad_word(word, interaction.guild_id, guild_settings):
            await interaction.followup.send(f"✅ Successfully added `{word}` to the bad word list for this guild.", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ `{word}` is already in this guild's bad word list.", ephemeral=True)

    @badword_group.command(name="remove", description="Remove a word from the auto-moderation list.")
    @checks.has_permissions(manage_guild=True)
    async def badword_remove(interaction: discord.Interaction, word: str):
        await interaction.response.defer(ephemeral=True)
        await ensure_guild_settings_in_cache(interaction.guild_id)
        guild_settings = automod._guild_settings_cache.get(interaction.guild_id)
        if await remove_bad_word(word, interaction.guild_id, guild_settings):
            await interaction.followup.send(f"🗑️ Successfully removed `{word}` from this guild's bad word list.", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ `{word}` was not found in this guild's bad word list.", ephemeral=True)

    @badword_group.command(name="view", description="View all words in the auto-moderation list.")
    @checks.has_permissions(manage_guild=True)
    async def badword_view(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await ensure_guild_settings_in_cache(interaction.guild_id)
        guild_settings = automod._guild_settings_cache.get(interaction.guild_id)
        words = await get_bad_words(interaction.guild_id, guild_settings)
        if words:
            await interaction.followup.send(f"🚫 Current bad words for this guild: {', '.join(words)}", ephemeral=True)
        else:
            await interaction.followup.send("✅ No bad words are currently set for this guild.", ephemeral=True)

    # --- REGISTER ALL COMMANDS ---
    bot.tree.add_command(roll)
    bot.tree.add_command(flip)
    bot.tree.add_command(status)
    
    bot.tree.add_command(mute)
    bot.tree.add_command(kick)
    bot.tree.add_command(ban)
    bot.tree.add_command(softban) # <-- Registered the new command here
    
    bot.tree.add_command(add_exception)
    bot.tree.add_command(remove_exception)
    bot.tree.add_command(view_exceptions)
    bot.tree.add_command(badword_group)
