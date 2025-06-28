import random
import discord
from discord import app_commands

async def setup_slash_commands(bot: discord.Client):
    @app_commands.command(name="roll", description="Roll a dice 🎲")
    async def roll(interaction: discord.Interaction):
        result = random.randint(1, 6)
        await interaction.response.send_message(f"🎲 You rolled a **{result}**!")

    @app_commands.command(name="flip", description="Flip a coin 🪙")
    async def flip(interaction: discord.Interaction):
        result = random.choice(["Heads", "Tails"])
        await interaction.response.send_message(f"🪙 You got **{result}**!")

    @bot.tree.command(name="status", description="Check Lumi's status 📊")
async def status(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(
        f"🛰️ Online as **{bot.user.name}**\n"
        f"📡 Latency: `{latency}ms`\n"
        f"🧠 Model: LLaMA-3 (via Groq API)"
    )


    # Register commands
    bot.tree.add_command(roll)
    bot.tree.add_command(flip)
