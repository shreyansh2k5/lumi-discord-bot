# slash_commands.py

import random
import discord
from discord import app_commands
from discord.ext.commands import Bot

def setup_slash_commands(bot: Bot):
    # /roll - Rolls a dice
    @bot.tree.command(name="roll", description="🎲 Roll a 6-sided dice")
    async def roll(interaction: discord.Interaction):
        result = random.randint(1, 6)
        await interaction.response.send_message(f"🎲 You rolled a **{result}**!")

    # /flip - Flips a coin
    @bot.tree.command(name="flip", description="🪙 Flip a coin")
    async def flip(interaction: discord.Interaction):
        result = random.choice(["Heads", "Tails"])
        await interaction.response.send_message(f"🪙 It's **{result}**!")
