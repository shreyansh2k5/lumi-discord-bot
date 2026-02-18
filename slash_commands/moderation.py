import discord
from discord import app_commands
from discord.ext import commands
from discord.app_commands import Choice
from datetime import timedelta

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # The Global Error Handler in main.py covers permissions, 
    # but you can keep this here for Cog-specific listener logic if needed.
    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            if not interaction.response.is_done():
                await interaction.response.send_message("🚫 You don't have permission to do that!", ephemeral=True)
            else:
                await interaction.followup.send("🚫 You don't have permission to do that!", ephemeral=True)

    @app_commands.command(name="mute", description="Mute (timeout) a user 🤫")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(member="The user to mute", duration="Duration in minutes", reason="Reason for muting")
    async def mute(self, interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = None):
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

    @app_commands.command(name="unmute", description="Unmute a user 🔊")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer()
        try:
            await member.timeout(None)
            await interaction.followup.send(f"🔊 Successfully unmuted {member.mention}.")
        except discord.Forbidden:
            await interaction.followup.send(f"⚠️ I cannot unmute {member.mention}.")

    @app_commands.command(name="kick", description="Kick a user from the server 🥾")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(member="The user to kick", reason="Reason for kicking")
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
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
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(member="The user to ban", delete_messages="Time period of messages to delete", reason="Reason for banning")
    @app_commands.choices(delete_messages=[
        Choice(name="Don't delete any", value=0),
        Choice(name="Last 10 minutes", value=600),
        Choice(name="Last 30 minutes", value=1800),
        Choice(name="Last 1 hour", value=3600),
        Choice(name="Last 24 hours", value=86400)
    ])
    async def ban(self, interaction: discord.Interaction, member: discord.Member, delete_messages: Choice[int], reason: str = None):
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
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(member="The user to softban", delete_messages="Time period of messages to delete", reason="Reason for softbanning")
    @app_commands.choices(delete_messages=[
        Choice(name="Last 10 minutes", value=600),
        Choice(name="Last 30 minutes", value=1800),
        Choice(name="Last 1 hour", value=3600),
        Choice(name="Last 24 hours", value=86400)
    ])
    async def softban(self, interaction: discord.Interaction, member: discord.Member, delete_messages: Choice[int], reason: str = None):
        await interaction.response.defer()

        dm_message = f"You have been kicked from **{interaction.guild.name}** and your recent messages were deleted."
        if reason: dm_message += f"\n**Reason:** {reason}"
        try:
            await member.send(dm_message)
        except discord.Forbidden:
            pass

        try:
            await member.ban(reason=reason, delete_message_seconds=delete_messages.value)
            await interaction.guild.unban(member, reason="Softban complete (auto-unban)")
            await interaction.followup.send(f"🧹 Successfully softbanned **{member.name}** (Kicked and messages deleted).")
        except discord.Forbidden:
            await interaction.followup.send(f"⚠️ I cannot softban {member.mention}.")

    @app_commands.command(name="message", description="Send a DM to a user through Lumi 💌")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(member="The user to message", content="What should I say?")
    async def message_user(self, interaction: discord.Interaction, member: discord.Member, content: str):
        await interaction.response.defer(ephemeral=True)
        
        try:
            embed = discord.Embed(
                description=content,
                color=discord.Color.from_rgb(255, 182, 193) # Lumi Pink
            )
            embed.set_author(name=f"Message from {interaction.guild.name}", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
            embed.set_footer(text="Sent via Lumi Bot")

            await member.send(embed=embed)
            await interaction.followup.send(f"✅ Message successfully sent to {member.mention}!", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send(f"❌ I couldn't DM {member.mention}. They might have their DMs closed!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ An error occurred: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Moderation(bot))