# cogs/basic.py

import discord
from discord import app_commands
from discord.ext import commands
import time


class Basic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="status", description="Check Lumi's status 📊")
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer()
        uptime_secs = int(time.time() - self.bot.start_time)
        hours, rem  = divmod(uptime_secs, 3600)
        minutes, secs = divmod(rem, 60)
        await interaction.followup.send(
            f"🛰️ Online as **{self.bot.user.name}**\n"
            f"⏱️ Uptime: `{hours}h {minutes}m {secs}s`\n"
            f"📡 Latency: `{round(self.bot.latency * 1000)}ms`\n"
            f"🏠 Servers: `{len(self.bot.guilds)}`"
        )

    @app_commands.command(name="server_info", description="Get information about this server 🏰")
    async def server_info(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild      = interaction.guild
        total      = guild.member_count
        bots       = sum(m.bot for m in guild.members)
        created_ts = int(guild.created_at.timestamp())
        owner      = guild.owner

        embed = discord.Embed(title=f"✨ {guild.name}", color=discord.Color.from_rgb(255, 182, 193))
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="👑 Owner",      value=f"{owner.mention} ({owner.name})", inline=False)
        embed.add_field(name="📅 Created",    value=f"<t:{created_ts}:D> (<t:{created_ts}:R>)", inline=True)
        embed.add_field(name="👥 Members",    value=f"Total: **{total}** | Humans: **{total - bots}** | Bots: **{bots}**", inline=True)
        embed.set_footer(text=f"Server ID: {guild.id}", icon_url=owner.avatar.url if owner.avatar else None)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Basic(bot))
