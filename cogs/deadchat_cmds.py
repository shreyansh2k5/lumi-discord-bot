# cogs/deadchat_cmds.py

import discord
from discord import app_commands
from discord.ext import commands
import moderation.automod as automod


class DeadChatCmds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    deadchat_group = app_commands.Group(name="deadchat", description="Configure dead-chat revival channels. 💬")

    @deadchat_group.command(name="add", description="Allow Lumi to revive dead chat in a channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(channel="Channel Lumi should message when chat goes quiet")
    async def add_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        await automod.ensure_guild_settings_in_cache(interaction.guild_id)
        gs = automod._guild_settings_cache.get(interaction.guild_id)
        if await automod.add_revive_channel(interaction.guild_id, channel.id, gs):
            await interaction.followup.send(f"✅ Lumi will revive dead chat in {channel.mention}!", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ {channel.mention} is already in the list.", ephemeral=True)

    @deadchat_group.command(name="remove", description="Stop Lumi from messaging in a channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(channel="Channel to remove")
    async def remove_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        await automod.ensure_guild_settings_in_cache(interaction.guild_id)
        gs = automod._guild_settings_cache.get(interaction.guild_id)
        if await automod.remove_revive_channel(interaction.guild_id, channel.id, gs):
            await interaction.followup.send(f"🗑️ Removed {channel.mention} from the dead chat list.", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ {channel.mention} wasn't in the list.", ephemeral=True)

    @deadchat_group.command(name="view", description="See all configured revival channels")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def view_channels(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await automod.ensure_guild_settings_in_cache(interaction.guild_id)
        gs  = automod._guild_settings_cache.get(interaction.guild_id)
        ids = automod.get_revive_channels(interaction.guild_id, gs)
        if not ids:
            return await interaction.followup.send("💤 No channels set. Use `/deadchat add` to configure one.", ephemeral=True)
        mentions = []
        for cid in ids:
            ch = interaction.guild.get_channel(cid)
            mentions.append(ch.mention if ch else f"~~`{cid}`~~ *(deleted)*")
        await interaction.followup.send("💬 Revival channels:\n" + "\n".join(f"• {m}" for m in mentions), ephemeral=True)


    @deadchat_group.command(name="interval", description="Set how long chat must be dead before Lumi revives it ⏱️")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(minutes="Minutes of silence before Lumi sends a revival message (min: 10, max: 1440)")
    async def set_interval(self, interaction: discord.Interaction, minutes: int):
        await interaction.response.defer(ephemeral=True)

        if minutes < 10:
            return await interaction.followup.send(
                "❌ Minimum interval is **10 minutes**.", ephemeral=True
            )
        if minutes > 1440:
            return await interaction.followup.send(
                "❌ Maximum interval is **1440 minutes** (24 hours).", ephemeral=True
            )

        await automod.ensure_guild_settings_in_cache(interaction.guild_id)
        gs = automod._guild_settings_cache.get(interaction.guild_id)
        await automod.set_revive_threshold(interaction.guild_id, minutes, gs)

        # Format a human-readable label
        if minutes >= 60 and minutes % 60 == 0:
            label = f"{minutes // 60}h"
        elif minutes >= 60:
            label = f"{minutes // 60}h {minutes % 60}m"
        else:
            label = f"{minutes}m"

        await interaction.followup.send(
            f"⏱️ Dead chat interval set to **{label}**."
            f"Lumi will revive chat after **{minutes} minutes** of silence.",
            ephemeral=True
        )

    @deadchat_group.command(name="settings", description="View all dead chat settings for this server 📋")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def view_settings(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await automod.ensure_guild_settings_in_cache(interaction.guild_id)
        gs = automod._guild_settings_cache.get(interaction.guild_id)

        # Channels
        ids = automod.get_revive_channels(interaction.guild_id, gs)
        if ids:
            channel_list = []
            for cid in ids:
                ch = interaction.guild.get_channel(cid)
                channel_list.append(ch.mention if ch else f"~~`{cid}`~~ *(deleted)*")
            channels_str = ", ".join(channel_list)
        else:
            channels_str = "*None set — use `/deadchat add`*"

        # Threshold
        minutes = automod.get_revive_threshold(interaction.guild_id, gs)
        if minutes >= 60 and minutes % 60 == 0:
            threshold_str = f"{minutes // 60}h"
        elif minutes >= 60:
            threshold_str = f"{minutes // 60}h {minutes % 60}m"
        else:
            threshold_str = f"{minutes}m"

        embed = discord.Embed(title="💬  Dead Chat Settings", color=discord.Color.from_rgb(255, 182, 193))
        embed.add_field(name="⏱️ Silence Interval", value=f"`{threshold_str}` of inactivity before Lumi revives", inline=False)
        embed.add_field(name="📢 Revival Channels", value=channels_str, inline=False)
        embed.set_footer(text="Use /deadchat interval and /deadchat add to configure")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(DeadChatCmds(bot))
