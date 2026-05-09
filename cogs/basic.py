# cogs/basic.py

import discord
from discord import app_commands
from discord.ext import commands
import time


class Basic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

# ── HELP ─────────────────────────────────────────────────────

    @commands.hybrid_command(name="help", description="Full list of Lumi commands 📖")
    async def help_command(self, ctx: commands.Context):
        embed = discord.Embed(
            title="✨  Lumi — Command Guide",
            description="Use `$command` or `/command` — both work!\nAdmin-only commands are marked with 🔒",
            color=PINK
        )
        embed.add_field(name="💰 Economy", value=(
            "`daily` — Claim 5,000 coins every 24h\n"
            "`beg` — Beg for random coins (5m cooldown)\n"
            "`balance` — Check your wallet\n"
            "`give <@user> <amt>` — Send coins to someone\n"
            "`profile` — View your stats & pets\n"
            "`leaderboard` — Top 10 richest users"
        ), inline=False)
        embed.add_field(name="🎲 Games", value=(
            "`blackjack <bet>` — Play 21 against Lumi\n"
            "`flip <bet>` — 50/50 coin flip\n"
            "`roll <bet>` — Roll a dice (6 = 6x jackpot!)\n"
            "`raid <@user>` — Steal up to 25% of their wallet"
        ), inline=False)
        embed.add_field(name="🛡️ Bank", value=(
            "`bank_deposit` — Safe Mode: immune to raids for 24h\n"
            "`bank_withdraw` — Leave Safe Mode"
        ), inline=False)
        embed.add_field(name="🐾 Pet Shop", value=(
            "`shop` — Browse available pets\n"
            "`shop buy <pet>` — Adopt a pet"
        ), inline=False)
        embed.add_field(name="🎵 Music", value=(
            "`play <song/URL>` — Play from YouTube\n"
            "`play` — Show all music commands\n"
            "`search <query>` — Pick from 5 results\n"
            "`skip` — Skip current song\n"
            "`pause` / `resume` — Toggle pause\n"
            "`remove` — Remove last queued song"
        ), inline=False)
        embed.add_field(name="ℹ️ Server", value=(
            "`/status` — Lumi's uptime & latency\n"
            "`/server_info` — Info about this server"
        ), inline=False)
        embed.add_field(name="🔒 Admin Only", value=(
            "`/mute` `/unmute` `/kick` `/ban`\n"
            "`/badword` — Manage word filter\n"
            "`/deadchat` — Configure dead chat revival\n"
            "`/exception` — Manage filter-exempt roles"
        ), inline=False)
        embed.set_footer(text="Tip: @mention or reply to Lumi to chat with her! 🌸")
        await ctx.send(embed=embed)



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
