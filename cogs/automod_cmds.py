# cogs/automod_cmds.py

import discord
from discord import app_commands
from discord.ext import commands
import moderation.automod as automod


class AutoModCmds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    badword_group  = app_commands.Group(name="badword",   description="Manage auto-moderated words. 🚫")
    exception_group = app_commands.Group(name="exception", description="Manage excluded roles. 🛡️")

    # ── Exception roles ──────────────────────────────────────────

    @exception_group.command(name="add", description="Exclude a role from auto-moderation")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_exception(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        await automod.ensure_guild_settings_in_cache(interaction.guild_id)
        gs = automod._guild_settings_cache.get(interaction.guild_id)
        if await automod.add_exception_role(interaction.guild_id, role.name, gs):
            await interaction.followup.send(f"✅ `{role.name}` is now excluded from moderation.", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ `{role.name}` is already exempted.", ephemeral=True)

    @exception_group.command(name="remove", description="Remove a role from the exception list")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_exception(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        await automod.ensure_guild_settings_in_cache(interaction.guild_id)
        gs = automod._guild_settings_cache.get(interaction.guild_id)
        if await automod.remove_exception_role(interaction.guild_id, role.name, gs):
            await interaction.followup.send(f"🗑️ `{role.name}` removed from exception list.", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ `{role.name}` was not in the exception list.", ephemeral=True)

    @exception_group.command(name="view", description="View all excluded roles")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def view_exceptions(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await automod.ensure_guild_settings_in_cache(interaction.guild_id)
        gs    = automod._guild_settings_cache.get(interaction.guild_id)
        roles = await automod.get_exempt_roles(interaction.guild_id, gs)
        if roles:
            await interaction.followup.send(f"🛡️ Exempted roles: {', '.join(roles)}", ephemeral=True)
        else:
            await interaction.followup.send("✅ No roles are currently exempted.", ephemeral=True)

    # ── Bad words ─────────────────────────────────────────────────

    @badword_group.command(name="add", description="Add a word to the moderation list")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def badword_add(self, interaction: discord.Interaction, word: str):
        await interaction.response.defer(ephemeral=True)
        await automod.ensure_guild_settings_in_cache(interaction.guild_id)
        gs = automod._guild_settings_cache.get(interaction.guild_id)
        if await automod.add_bad_word(word, interaction.guild_id, gs):
            await interaction.followup.send(f"✅ Added `{word}` to the bad word list.", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ `{word}` is already in the list.", ephemeral=True)

    @badword_group.command(name="remove", description="Remove a word from the moderation list")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def badword_remove(self, interaction: discord.Interaction, word: str):
        await interaction.response.defer(ephemeral=True)
        await automod.ensure_guild_settings_in_cache(interaction.guild_id)
        gs = automod._guild_settings_cache.get(interaction.guild_id)
        if await automod.remove_bad_word(word, interaction.guild_id, gs):
            await interaction.followup.send(f"🗑️ Removed `{word}` from the list.", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ `{word}` was not found.", ephemeral=True)

    @badword_group.command(name="view", description="View all moderated words")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def badword_view(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await automod.ensure_guild_settings_in_cache(interaction.guild_id)
        gs    = automod._guild_settings_cache.get(interaction.guild_id)
        words = await automod.get_bad_words(interaction.guild_id, gs)
        if words:
            await interaction.followup.send(f"🚫 Bad words: {', '.join(words)}", ephemeral=True)
        else:
            await interaction.followup.send("✅ No bad words currently set.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(AutoModCmds(bot))
