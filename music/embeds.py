# music/embeds.py
# Now-Playing embed builder for the native Python (yt-dlp) player.
# Previously imported wavelink — that dependency is GONE.
import discord
from core.embeds import PINK
from music.ytdl import format_duration


def build_np_embed(
    current: dict,
    queue_len: int,
    paused: bool,
    loop: bool,
    volume_pct: int,
) -> discord.Embed:
    """
    Build the Now Playing embed shown in the MusicControlView message.

    Parameters match what music/views.py passes:
        build_np_embed(p.current, len(p.queue), p.paused, p.loop, p.volume_pct)
    """
    if not current:
        return discord.Embed(description="Nothing playing.", color=PINK)

    title   = current.get("title", "Unknown")
    url     = current.get("webpage_url", "")
    dur     = current.get("duration", 0)
    thumb   = current.get("thumbnail", "")
    req     = current.get("requester", "Unknown")

    desc = f"**[{title}]({url})**" if url else f"**{title}**"
    embed = discord.Embed(title="🎵  Now Playing", description=desc, color=PINK)

    embed.add_field(name="⏱ Duration",   value=format_duration(dur),   inline=True)
    embed.add_field(name="👤 Requester", value=req,                     inline=True)

    status = []
    if paused:
        status.append("⏸ Paused")
    if loop:
        status.append("🔁 Loop")
    status.append(f"📋 Queue: {queue_len}")
    embed.add_field(name="Status", value=" · ".join(status), inline=False)

    if thumb:
        embed.set_thumbnail(url=thumb)
    embed.set_footer(text="Lumi Music 🎶  •  Use the buttons to control playback")
    return embed