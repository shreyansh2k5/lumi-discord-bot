import discord
from discord import app_commands
from discord.ext import commands
import time

class Basic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="status", description="Check Lumi's status 📊")
    async def status(self, interaction: discord.Interaction): # Added 'self'
        await interaction.response.defer()
        
        # 1. Calculate Uptime using the start_time we attached to the bot
        uptime_seconds = int(time.time() - self.bot.start_time) 
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s"

        # 2. Get Bot Stats using self.bot
        latency = round(self.bot.latency * 1000)
        server_count = len(self.bot.guilds) 
        
        # 3. Send Response
        await interaction.followup.send(
            f"🛰️ Online as **{self.bot.user.name}**\n"
            f"⏱️ Uptime: `{uptime_str}`\n"
            f"📡 Latency: `{latency}ms`\n"
            f"🏠 Servers: `{server_count}`\n"
        )

    @app_commands.command(name="server_info", description="Get detailed information about this server 🏰")
    async def server_info(self, interaction: discord.Interaction): # Added 'self'
        await interaction.response.defer()
        
        guild = interaction.guild
        
        # 1. Member and Bot counts
        total_members = guild.member_count
        num_bots = sum(member.bot for member in guild.members)
        num_humans = total_members - num_bots
        
        # 2. Server Age calculation
        creation_date = guild.created_at
        creation_timestamp = int(creation_date.timestamp())
        
        # 3. Owner information
        owner = guild.owner
        
        # Create the Embed
        embed = discord.Embed(
            title=f"✨ {guild.name} Information",
            color=discord.Color.from_rgb(255, 182, 193) # Lumi Pink
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
            
        embed.add_field(name="👑 Owner", value=f"{owner.mention} ({owner.name})", inline=False)
        embed.add_field(name="📅 Created On", value=f"<t:{creation_timestamp}:D>\n(<t:{creation_timestamp}:R>)", inline=True)
        embed.add_field(name="👥 Members", value=f"Total: **{total_members}**\nHumans: **{num_humans}**\nBots: **{num_bots}**", inline=True)
        
        if owner.avatar:
            embed.set_footer(text=f"Server ID: {guild.id}", icon_url=owner.avatar.url)
        else:
            embed.set_footer(text=f"Server ID: {guild.id}")

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Basic(bot))