import random
import discord
from discord import app_commands
from automod import add_exception_role, get_exempt_roles

async def setup_slash_commands(bot: discord.Client):
    @app_commands.command(name="roll", description="Roll a dice 🎲")
    async def roll(interaction: discord.Interaction):
        result = random.randint(1, 6)
        await interaction.response.send_message(f"🎲 You rolled a **{result}**!")

    @app_commands.command(name="flip", description="Flip a coin 🪙")
    async def flip(interaction: discord.Interaction):
        result = random.choice(["Heads", "Tails"])
        await interaction.response.send_message(f"🪙 You got **{result}**!")

    # 📊 /status
    @bot.tree.command(name="status", description="Check Lumi's status 📊")
    async def status(interaction: discord.Interaction):
        latency = round(bot.latency * 1000)
        await interaction.response.send_message(
            f"🛰️ Online as **{bot.user.name}**\n"
            f"📡 Latency: `{latency}ms`\n"
            f"🧠 Model: LLaMA-3 (via Groq API)"
        )

  @app_commands.command(name="add_exception_role", description="Exclude a role from auto-moderation")
    @app_commands.describe(role="Role to exclude from moderation")
    async def add_exception(interaction: discord.Interaction, role: discord.Role):
        add_exception_role(interaction.guild_id, role.name)
        await interaction.response.send_message(f"✅ `{role.name}` will now be excluded from moderation.")

    @app_commands.command(name="view_exceptions", description="View currently excluded roles from moderation")
    async def view_exceptions(interaction: discord.Interaction):
        roles = get_exempt_roles(interaction.guild_id)
        if roles:
            await interaction.response.send_message(f"🚫 Exempted roles: {', '.join(roles)}")
        else:
            await interaction.response.send_message("✅ No roles are currently exempted.")

    # Register all commands
    bot.tree.add_command(roll)
    bot.tree.add_command(flip)
    bot.tree.add_command(status)
    bot.tree.add_command(add_exception)
    bot.tree.add_command(view_exceptions)
