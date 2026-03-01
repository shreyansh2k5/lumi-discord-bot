# cogs/fun.py

import discord
from discord import app_commands
from discord.ext import commands


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="meme", description="Get a random meme 😂")
    async def meme(self, interaction: discord.Interaction):
        await interaction.response.send_message("Meme feature coming soon! ✨")


async def setup(bot):
    await bot.add_cog(Fun(bot))
