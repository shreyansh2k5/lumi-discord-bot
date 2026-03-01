# main.py
# Entry point — only responsible for wiring modules together and starting the bot.

from dotenv import load_dotenv
load_dotenv()

import os
import sys
from pathlib import Path
import discord
from discord import app_commands

# Make sure imports always work relative to this file's location,
# regardless of which directory Python is launched from.
ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from bot.client import get_client, revive_chat_loop
import bot.events  # registers on_message, on_command_error, on_member_join
from core.keep_alive import keep_alive
from services.database import init_firebase
from config import COMMAND_PREFIX

# Optional presence
try:
    from bot.presence import set_rich_presence
except ImportError:
    set_rich_presence = None

# ── Initialise Firebase ──────────────────────────────────────────
init_firebase()

# ── Bot instance ─────────────────────────────────────────────────
bot = get_client()

@bot.event
async def on_ready():
    import time
    bot.start_time = time.time()  # used by /status command
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

    # ── Global slash-command error handler ──────────────────────
    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.MissingPermissions):
            message = "🚫 You don't have permission to use this!"
        elif isinstance(error, app_commands.CommandOnCooldown):
            message = f"⏳ Please wait `{error.retry_after:.1f}s` before using this again."
        else:
            message = "⚠️ An unexpected error occurred!"
            print(f"[SlashError] {error}")

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    # ── Auto-load all cogs ──────────────────────────────────────
    for filename in os.listdir(ROOT / 'cogs'):
        if filename.endswith('.py') and filename != '__init__.py':
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f"  📦 Loaded cog: {filename}")
            except Exception as e:
                print(f"  ❌ Failed to load cogs/{filename}: {e}")

    # ── Sync slash commands ─────────────────────────────────────
    await bot.tree.sync()
    print("🌐 Command tree synced.")

    # ── Start background loops ──────────────────────────────────
    if not revive_chat_loop.is_running():
        revive_chat_loop.start()
        print("💬 Dead-chat revival loop started.")

    if set_rich_presence:
        try:
            await set_rich_presence(bot)
        except Exception as e:
            print(f"[Warning] Rich presence error: {e}")


keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
