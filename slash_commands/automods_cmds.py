import discord
from discord import app_commands
from discord.ext import commands
import automod

class AutoModCmds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Define the Groups
    badword_group = app_commands.Group(name="badword", description="Manage auto-moderated words. 🚫")
    exception_group = app_commands.Group(name="exception", description="Manage excluded roles. 🛡️")

    # --- EXCEPTION ROLE COMMANDS ---

    @exception_group.command(name="add", description="Exclude a role from auto-moderation")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_exception(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        await automod.ensure_guild_settings_in_cache(interaction.guild_id)
        guild_settings = automod._guild_settings_cache.get(interaction.guild_id)
        
        if await automod.add_exception_role(interaction.guild_id, role.name, guild_settings):
            await interaction.followup.send(f"✅ `{role.name}` will now be excluded from moderation.", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ `{role.name}` is already an exempted role.", ephemeral=True)

    @exception_group.command(name="remove", description="Remove a role from exception list")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_exception(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        await automod.ensure_guild_settings_in_cache(interaction.guild_id)
        guild_settings = automod._guild_settings_cache.get(interaction.guild_id)
        
        if await automod.remove_exception_role(interaction.guild_id, role.name, guild_settings):
            await interaction.followup.send(f"🗑️ `{role.name}` removed from exception list.", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ `{role.name}` was not found in the exception list.", ephemeral=True)

    @exception_group.command(name="view", description="View excluded roles from moderation")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def view_exceptions(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await automod.ensure_guild_settings_in_cache(interaction.guild_id)
        guild_settings = automod._guild_settings_cache.get(interaction.guild_id)
        
        roles = await automod.get_exempt_roles(interaction.guild_id, guild_settings)
        if roles:
            await interaction.followup.send(f"🚫 Exempted roles: {', '.join(roles)}", ephemeral=True)
        else:
            await interaction.followup.send("✅ No roles are currently exempted.", ephemeral=True)

    # --- BAD WORD COMMANDS ---

    @badword_group.command(name="add", description="Add a word to the auto-moderation list.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def badword_add(self, interaction: discord.Interaction, word: str):
        await interaction.response.defer(ephemeral=True)
        await automod.ensure_guild_settings_in_cache(interaction.guild_id)
        guild_settings = automod._guild_settings_cache.get(interaction.guild_id)
        
        if await automod.add_bad_word(word, interaction.guild_id, guild_settings):
            await interaction.followup.send(f"✅ Successfully added `{word}` to the bad word list.", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ `{word}` is already in the list.", ephemeral=True)

    @badword_group.command(name="remove", description="Remove a word from the auto-moderation list.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def badword_remove(self, interaction: discord.Interaction, word: str):
        await interaction.response.defer(ephemeral=True)
        await automod.ensure_guild_settings_in_cache(interaction.guild_id)
        guild_settings = automod._guild_settings_cache.get(interaction.guild_id)
        
        if await automod.remove_bad_word(word, interaction.guild_id, guild_settings):
            await interaction.followup.send(f"🗑️ Successfully removed `{word}` from the list.", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ `{word}` was not found in the list.", ephemeral=True)

    @badword_group.command(name="view", description="View all words in the auto-moderation list.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def badword_view(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await automod.ensure_guild_settings_in_cache(interaction.guild_id)
        guild_settings = automod._guild_settings_cache.get(interaction.guild_id)
        
        words = await automod.get_bad_words(interaction.guild_id, guild_settings)
        if words:
            await interaction.followup.send(f"🚫 Current bad words: {', '.join(words)}", ephemeral=True)
        else:
            await interaction.followup.send("✅ No bad words are currently set.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AutoModCmds(bot))