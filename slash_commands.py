import random
import discord
from discord import app_commands
from automod import (
    # These functions are now async, so they need to be awaited
    add_exception_role, get_exempt_roles, remove_exception_role,
    add_bad_word, remove_bad_word, get_bad_words
)
from discord.app_commands import checks


async def setup_slash_commands(bot: discord.Client):
    @app_commands.command(name="roll", description="Roll a dice 🎲")
    async def roll(interaction: discord.Interaction):
        result = random.randint(1, 6)
        await interaction.response.send_message(f"🎲 You rolled a **{result}**!")

    @app_commands.command(name="flip", description="Flip a coin 🪙")
    async def flip(interaction: discord.Interaction):
        result = random.choice(["Heads", "Tails"])
        await interaction.response.send_message(f"🪙 You got **{result}**!")

    @app_commands.command(name="status", description="Check Lumi's status 📊")
    async def status(interaction: discord.Interaction):
        latency = round(bot.latency * 1000)
        await interaction.response.send_message(
            f"🛰️ Online as **{bot.user.name}**\n"
            f"📡 Latency: `{latency}ms`\n"
            f"🧠 Model: LLaMA-3 (via Groq API)"
        )

    # Auto-moderation exception roles commands
    @app_commands.command(name="add_exception_role", description="Exclude a role from auto-moderation")
    @checks.has_permissions(manage_guild=True)
    @app_commands.describe(role="Role to exclude from moderation")
    async def add_exception(interaction: discord.Interaction, role: discord.Role):
        # Await the async function
        success = await add_exception_role(interaction.guild_id, role.name)
        if success:
            await interaction.response.send_message(
                f"✅ `{role.name}` will now be excluded from moderation.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"⚠️ `{role.name}` is already an exempted role.",
                ephemeral=True
            )


    @app_commands.command(name="remove_exception_role", description="Remove a role from exception list")
    @checks.has_permissions(manage_guild=True)
    @app_commands.describe(role="Role to remove from exception list")
    async def remove_exception(interaction: discord.Interaction, role: discord.Role):
        # Await the async function
        success = await remove_exception_role(interaction.guild_id, role.name)
        if success:
            await interaction.response.send_message(
                f"🗑️ `{role.name}` removed from exception list.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"⚠️ `{role.name}` was not found in the exception list.",
                ephemeral=True
            )


    @app_commands.command(name="view_exceptions", description="View excluded roles from moderation")
    @checks.has_permissions(manage_guild=True)
    async def view_exceptions(interaction: discord.Interaction):
        # Await the async function
        roles = await get_exempt_roles(interaction.guild_id)
        if roles:
            await interaction.response.send_message(
                f"🚫 Exempted roles: {', '.join(roles)}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "✅ No roles are currently exempted.",
                ephemeral=True
            )

    # --- Command Group: /badword ---
    badword_group = app_commands.Group(name="badword", description="Manage auto-moderated words. 🚫")

    @badword_group.command(name="add", description="Add a word to the auto-moderation list.")
    @checks.has_permissions(manage_guild=True)
    @app_commands.describe(word="The word to add.")
    async def badword_add(interaction: discord.Interaction, word: str):
        # Await the async function
        if await add_bad_word(word):
            await interaction.response.send_message(f"✅ Successfully added `{word}` to the bad word list.", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ `{word}` is already in the bad word list.", ephemeral=True)

    @badword_group.command(name="remove", description="Remove a word from the auto-moderation list.")
    @checks.has_permissions(manage_guild=True)
    @app_commands.describe(word="The word to remove.")
    async def badword_remove(interaction: discord.Interaction, word: str):
        # Await the async function
        if await remove_bad_word(word):
            await interaction.response.send_message(f"🗑️ Successfully removed `{word}` from the bad word list.", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ `{word}` was not found in the bad word list.", ephemeral=True)

    @badword_group.command(name="view", description="View all words in the auto-moderation list.")
    @checks.has_permissions(manage_guild=True)
    async def badword_view(interaction: discord.Interaction):
        # Await the async function
        words = await get_bad_words()
        if words:
            await interaction.response.send_message(
                f"🚫 Current bad words: {', '.join(words)}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "✅ No bad words are currently set.",
                ephemeral=True
            )

    # Register all commands and command groups to the bot's command tree
    bot.tree.add_command(roll)
    bot.tree.add_command(flip)
    bot.tree.add_command(status)
    bot.tree.add_command(add_exception)
    bot.tree.add_command(remove_exception)
    bot.tree.add_command(view_exceptions)
    bot.tree.add_command(badword_group)
