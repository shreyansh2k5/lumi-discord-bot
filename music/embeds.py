# music/embeds.py
import discord
from core.embeds import PINK
from music.ytdl import format_duration


def build_np_embed(track: dict, queue_len: int = 0, paused: bool = False, loop: bool = False, volume: int = 100) -> discord.Embed:
    embed = discord.Embed(
        title="🎵  Now Playing",
        description=f"**[{track['title']}]({track['webpage_url']})**",
        color=PINK
    )
    embed.add_field(name="⏱ Duration",  value=format_duration(track.get("duration", 0)), inline=True)
    embed.add_field(name="👤 Requester", value=track.get("requester", "Unknown"),         inline=True)
    embed.add_field(name="🔊 Volume",    value=f"{volume}%",                               inline=True)

    status = []
    if paused:  status.append("⏸ Paused")
    if loop:    status.append("🔁 Loop")
    status.append(f"📋 Queue: {queue_len}")
    embed.add_field(name="Status", value=" · ".join(status), inline=False)

    if track.get("thumbnail"):
        embed.set_thumbnail(url=track["thumbnail"])
    embed.set_footer(text="Lumi Music 🎶  •  Use the buttons to control playback")
    return embed