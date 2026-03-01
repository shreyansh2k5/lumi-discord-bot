# cogs/moderation.py

import discord
from discord import app_commands
from discord.ext import commands
from discord.app_commands import Choice
from datetime import timedelta


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            msg = "🚫 You don't have permission to do that!"
            if not interaction.response.is_done():
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.followup.send(msg, ephemeral=True)

    @app_commands.command(name="mute", description="Mute (timeout) a user 🤫")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(member="The user to mute", duration="Duration in minutes", reason="Reason for muting")
    async def mute(self, interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = None):
        await interaction.response.defer()
        dm = f"You have been muted in **{interaction.guild.name}** for {duration} minutes."
        if reason: dm += f"\n**Reason:** {reason}"
        try: await member.send(dm)
        except discord.Forbidden: pass
        try:
            await member.timeout(timedelta(minutes=duration), reason=reason)
            await interaction.followup.send(f"✅ Muted {member.mention} for {duration} minutes.")
        except discord.Forbidden:
            await interaction.followup.send(f"⚠️ Cannot mute {member.mention} — my role may be lower than theirs.")

    @app_commands.command(name="unmute", description="Unmute a user 🔊")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer()
        try:
            await member.timeout(None)
            await interaction.followup.send(f"🔊 Unmuted {member.mention}.")
        except discord.Forbidden:
            await interaction.followup.send(f"⚠️ Cannot unmute {member.mention}.")

    @app_commands.command(name="kick", description="Kick a user 🥾")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(member="The user to kick", reason="Reason for kicking")
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        await interaction.response.defer()
        dm = f"You have been kicked from **{interaction.guild.name}**."
        if reason: dm += f"\n**Reason:** {reason}"
        try: await member.send(dm)
        except discord.Forbidden: pass
        try:
            await member.kick(reason=reason)
            await interaction.followup.send(f"✅ Kicked **{member.name}**.")
        except discord.Forbidden:
            await interaction.followup.send(f"⚠️ Cannot kick {member.mention}.")

    @app_commands.command(name="ban", description="Ban a user 🔨")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(member="The user to ban", delete_messages="Time period of messages to delete", reason="Reason")
    @app_commands.choices(delete_messages=[
        Choice(name="Don't delete any",   value=0),
        Choice(name="Last 10 minutes",    value=600),
        Choice(name="Last 30 minutes",    value=1800),
        Choice(name="Last 1 hour",        value=3600),
        Choice(name="Last 24 hours",      value=86400),
    ])
    async def ban(self, interaction: discord.Interaction, member: discord.Member, delete_messages: Choice[int], reason: str = None):
        await interaction.response.defer()
        dm = f"You have been banned from **{interaction.guild.name}**."
        if reason: dm += f"\n**Reason:** {reason}"
        try: await member.send(dm)
        except discord.Forbidden: pass
        try:
            await member.ban(reason=reason, delete_message_seconds=delete_messages.value)
            await interaction.followup.send(f"✅ Banned **{member.name}**.")
        except discord.Forbidden:
            await interaction.followup.send(f"⚠️ Cannot ban {member.mention}.")

    @app_commands.command(name="softban", description="Softban a user (kick + delete messages) 🧹")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(member="The user to softban", delete_messages="Time period of messages to delete", reason="Reason")
    @app_commands.choices(delete_messages=[
        Choice(name="Last 10 minutes", value=600),
        Choice(name="Last 30 minutes", value=1800),
        Choice(name="Last 1 hour",     value=3600),
        Choice(name="Last 24 hours",   value=86400),
    ])
    async def softban(self, interaction: discord.Interaction, member: discord.Member, delete_messages: Choice[int], reason: str = None):
        await interaction.response.defer()
        dm = f"You have been kicked from **{interaction.guild.name}** and your recent messages were deleted."
        if reason: dm += f"\n**Reason:** {reason}"
        try: await member.send(dm)
        except discord.Forbidden: pass
        try:
            await member.ban(reason=reason, delete_message_seconds=delete_messages.value)
            await interaction.guild.unban(member, reason="Softban complete (auto-unban)")
            await interaction.followup.send(f"🧹 Softbanned **{member.name}**.")
        except discord.Forbidden:
            await interaction.followup.send(f"⚠️ Cannot softban {member.mention}.")

    @app_commands.command(name="message", description="Send a DM to a user through Lumi 💌")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(member="The user to message", content="What should I say?")
    async def message_user(self, interaction: discord.Interaction, member: discord.Member, content: str):
        await interaction.response.defer(ephemeral=True)
        try:
            embed = discord.Embed(description=content, color=discord.Color.from_rgb(255, 182, 193))
            embed.set_author(name=f"Message from {interaction.guild.name}", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
            embed.set_footer(text="Sent via Lumi Bot")
            await member.send(embed=embed)
            await interaction.followup.send(f"✅ Message sent to {member.mention}!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(f"❌ Couldn't DM {member.mention} — their DMs may be closed.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ Error: {e}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
