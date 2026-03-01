# core/embeds.py
# Shared embed helpers and colour constants used across all cogs.
# Import from here instead of defining colours/helpers in each command file.

import discord

# ── Shared colours ───────────────────────────────────────────────
PINK   = discord.Color.from_rgb(255, 182, 193)
GOLD   = discord.Color.from_rgb(255, 215, 0)
BLUE   = discord.Color.blue()
GREEN  = discord.Color.green()
RED    = discord.Color.red()


async def send_intro(
    ctx,
    emoji: str,
    title: str,
    description: str,
    color: discord.Color = PINK,
) -> discord.Message:
    """
    Sends a small 'loading' embed immediately so the user gets instant feedback,
    then returns the message so the caller can edit it with the real result.

    Usage:
        intro = await send_intro(ctx, "🎁", "Daily Reward", "*Checking account...*")
        # ... do async work ...
        await intro.edit(embed=result_embed)
    """
    embed = discord.Embed(title=f"{emoji}  {title}", description=description, color=color)
    embed.set_footer(text="Lumi Economy ✨")
    return await ctx.send(embed=embed)


def result_embed(
    title: str,
    description: str,
    color: discord.Color = PINK,
    author_name: str = "",
    author_icon: str = "",
) -> discord.Embed:
    """
    Builds a standard result embed.
    Optionally attaches the triggering user as the author.
    """
    e = discord.Embed(title=title, description=description, color=color)
    if author_name:
        e.set_author(name=author_name, icon_url=author_icon or discord.Embed.Empty)
    e.set_footer(text="Lumi Economy ✨")
    return e
