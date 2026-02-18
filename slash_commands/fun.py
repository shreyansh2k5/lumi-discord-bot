import discord
from discord import app_commands
from discord.ext import commands
import random

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="roll", description="Roll a dice 🎲")
    async def roll(self, interaction: discord.Interaction):
        result = random.randint(1, 6)
        await interaction.response.send_message(f"🎲 You rolled a **{result}**!")

    @app_commands.command(name="flip", description="Flip a coin 🪙")
    async def flip(self, interaction: discord.Interaction):
        result = random.choice(["Heads", "Tails"])
        await interaction.response.send_message(f"🪙 You got **{result}**!")

# This function is required for main.py to load this file
async def setup(bot):
    await bot.add_cog(Fun(bot))