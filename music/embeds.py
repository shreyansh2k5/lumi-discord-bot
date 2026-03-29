# music/embeds.py
import discord
import wavelink
from core.embeds import PINK


def format_duration(ms: int) -> str:
    if not ms:
        return "Live"
    s = ms // 1000
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02}:{sec:02}" if h else f"{m}:{sec:02}"


def build_np_embed(player: wavelink.Player) -> discord.Embed:
    t = player.current
    if not t:
        return discord.Embed(description="Nothing playing.", color=PINK)

    embed = discord.Embed(
        title="🎵  Now Playing",
        description=f"**[{t.title}]({t.uri})**",
        color=PINK
    )
    embed.add_field(name="⏱ Duration",
                    value=format_duration(t.length), inline=True)
    embed.add_field(name="👤 Requester",
                    value=getattr(getattr(t, "extras", None), "requester", "Unknown"), inline=True)
    embed.add_field(name="🔊 Volume",
                    value=f"{player.volume}%", inline=True)

    status = []
    if player.paused:
        status.append("⏸ Paused")
    if player.queue.mode == wavelink.QueueMode.loop:
        status.append("🔁 Loop")
    status.append(f"📋 Queue: {len(player.queue)}")
    embed.add_field(name="Status", value=" · ".join(status), inline=False)

    if t.artwork:
        embed.set_thumbnail(url=t.artwork)
    embed.set_footer(text="Lumi Music 🎶  •  Use the buttons to control playback")
    return embed