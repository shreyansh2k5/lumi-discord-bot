# cogs/music.py
# Uses wavelink 3 + free public Lavalink v4 server.
# Lavalink handles all YouTube streaming — no yt-dlp, no cookies, no IP issues.

import asyncio
import discord
import wavelink
from discord import app_commands
from discord.ext import commands

from core.embeds import PINK


# ── Free public Lavalink v4 nodes (tried in order) ───────────────
LAVALINK_NODES = [
    {"uri": "https://lavalinkv4.serenetia.com", "password": "https://dsc.gg/ajidevserver"},
    {"uri": "http://lavalinkv4.serenetia.com:80", "password": "https://dsc.gg/ajidevserver"},
    {"uri": "https://lavalink.serenetia.com",    "password": "https://dsc.gg/ajidevserver"},
]


def format_duration(ms: int) -> str:
    if not ms:
        return "Live"
    s = ms // 1000
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02}:{sec:02}" if h else f"{m}:{sec:02}"


# ── Now-playing embed ─────────────────────────────────────────────

def build_np_embed(player: wavelink.Player) -> discord.Embed:
    track = player.current
    if not track:
        return discord.Embed(description="Nothing playing.", color=PINK)

    embed = discord.Embed(
        title="🎵  Now Playing",
        description=f"**[{track.title}]({track.uri})**",
        color=PINK
    )
    embed.add_field(name="⏱ Duration",  value=format_duration(track.length), inline=True)
    embed.add_field(name="👤 Requester", value=getattr(track, "requester", "Unknown"), inline=True)

    status = []
    if player.paused:     status.append("⏸ Paused")
    if getattr(player, "loop_mode", False): status.append("🔁 Loop")
    queue_len = player.queue.count if hasattr(player.queue, "count") else len(player.queue)
    status.append(f"📋 Queue: {queue_len}")
    embed.add_field(name="Status", value=" · ".join(status), inline=False)

    if track.artwork:
        embed.set_thumbnail(url=track.artwork)

    embed.set_footer(text="Lumi Music 🎶  •  Use the buttons to control playback")
    return embed


# ── Control buttons ───────────────────────────────────────────────

class MusicControlView(discord.ui.View):
    def __init__(self, cog: "Music", guild_id: int):
        super().__init__(timeout=None)
        self.cog      = cog
        self.guild_id = guild_id

    def _player(self) -> wavelink.Player | None:
        guild = self.cog.bot.get_guild(self.guild_id)
        return guild.voice_client if guild else None

    async def _update_embed(self, interaction: discord.Interaction):
        player = self._player()
        if player and player.current:
            await interaction.response.edit_message(embed=build_np_embed(player), view=self)
        else:
            await interaction.response.edit_message(
                embed=discord.Embed(description="⏹ Playback stopped.", color=PINK), view=None
            )

    @discord.ui.button(emoji="⏮", style=discord.ButtonStyle.secondary, row=0)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self._player()
        if not player: return await interaction.response.send_message("Nothing playing!", ephemeral=True)
        await player.seek(0)
        await interaction.response.defer()

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=0)
    async def btn_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self._player()
        if not player: return await interaction.response.send_message("Nothing playing!", ephemeral=True)
        if player.queue.mode == wavelink.QueueMode.loop:
            player.queue.mode = wavelink.QueueMode.normal
            button.style = discord.ButtonStyle.secondary
        else:
            player.queue.mode = wavelink.QueueMode.loop
            button.style = discord.ButtonStyle.success
        await self._update_embed(interaction)

    @discord.ui.button(emoji="⏸", style=discord.ButtonStyle.primary, row=0)
    async def btn_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self._player()
        if not player: return await interaction.response.send_message("Nothing playing!", ephemeral=True)
        await player.pause(not player.paused)
        button.emoji = discord.PartialEmoji(name="▶" if player.paused else "⏸")
        button.style = discord.ButtonStyle.secondary if player.paused else discord.ButtonStyle.primary
        await self._update_embed(interaction)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, row=0)
    async def btn_shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self._player()
        if not player: return await interaction.response.send_message("Nothing playing!", ephemeral=True)
        player.queue.shuffle()
        button.style = discord.ButtonStyle.success
        await interaction.response.defer()

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.secondary, row=0)
    async def btn_skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self._player()
        if not player: return await interaction.response.send_message("Nothing playing!", ephemeral=True)
        await player.skip(force=True)
        await interaction.response.defer()

    @discord.ui.button(emoji="📋", style=discord.ButtonStyle.secondary, row=1)
    async def btn_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self._player()
        if not player or player.queue.is_empty:
            return await interaction.response.send_message("Queue is empty!", ephemeral=True)
        lines = [
            f"`{i}.` {t.title} ({format_duration(t.length)})"
            for i, t in enumerate(list(player.queue)[:10], 1)
        ]
        if len(player.queue) > 10:
            lines.append(f"*...and {len(player.queue) - 10} more*")
        embed = discord.Embed(title="📋  Queue", description="\n".join(lines), color=PINK)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(emoji="⏹", style=discord.ButtonStyle.danger, row=1)
    async def btn_stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self._player()
        if not player: return await interaction.response.send_message("Nothing playing!", ephemeral=True)
        await player.disconnect()
        await interaction.response.edit_message(
            embed=discord.Embed(description="⏹ Stopped and disconnected.", color=PINK), view=None
        )


# ── Search dropdown ───────────────────────────────────────────────

class SearchSelect(discord.ui.Select):
    def __init__(self, cog: "Music", tracks: list[wavelink.Playable], requester: str):
        self.cog       = cog
        self.tracks    = tracks
        self.requester = requester
        options = [
            discord.SelectOption(
                label=t.title[:100],
                description=f"{format_duration(t.length)} · {t.author[:40]}"[:100],
                value=str(i)
            )
            for i, t in enumerate(tracks)
        ]
        super().__init__(placeholder="🎵 Pick a song...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        track = self.tracks[int(self.values[0])]
        track.extras = wavelink.ExtrasNamespace({"requester": self.requester})
        await interaction.message.edit(
            embed=discord.Embed(description=f"✅ **{track.title}** added!", color=PINK), view=None
        )
        if not interaction.user.voice:
            return await interaction.followup.send("Join a voice channel first!", ephemeral=True)
        player: wavelink.Player = interaction.guild.voice_client  # type: ignore
        if not player:
            player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
        if player.playing:
            await player.queue.put_wait(track)
            await self.cog._move_np(player, interaction.channel)
        else:
            await player.queue.put_wait(track)
            await player.play(player.queue.get())
            await self.cog._send_np(player, interaction.channel)


class SearchView(discord.ui.View):
    def __init__(self, cog: "Music", tracks: list, requester: str):
        super().__init__(timeout=30)
        self.add_item(SearchSelect(cog, tracks, requester))


# ── Music Cog ─────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """Connect to Lavalink nodes when cog loads."""
        nodes = []
        for n in LAVALINK_NODES:
            nodes.append(wavelink.Node(uri=n["uri"], password=n["password"]))
        try:
            await wavelink.Pool.connect(nodes=nodes, client=self.bot, cache_capacity=100)
            print(f"[Music] ✅ Connected to Lavalink")
        except Exception as e:
            print(f"[Music] ❌ Lavalink connection failed: {e}")

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f"[Music] Node ready: {payload.node.uri}")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player = payload.player
        if not player:
            return
        channel = getattr(player, "_text_channel", None)
        if not player.queue.is_empty:
            track = player.queue.get()
            await player.play(track)
            if channel:
                await self._move_np(player, channel)
        else:
            if player.now_playing_msg:
                try:
                    await player.now_playing_msg.edit(
                        embed=discord.Embed(description="✅ Queue finished!", color=PINK), view=None
                    )
                except Exception:
                    pass

    async def _send_np(self, player: wavelink.Player, channel):
        """Delete old now-playing message and send a new one at the bottom."""
        if hasattr(player, "now_playing_msg") and player.now_playing_msg:
            try:
                await player.now_playing_msg.delete()
            except Exception:
                pass
        embed = build_np_embed(player)
        view  = MusicControlView(self, channel.guild.id)
        player.now_playing_msg = await channel.send(embed=embed, view=view)
        player._text_channel   = channel

    async def _move_np(self, player: wavelink.Player, channel):
        """Alias for _send_np — always sends controls at bottom."""
        await self._send_np(player, channel)

    # ── $play / /play ─────────────────────────────────────────────

    @commands.hybrid_command(name="play", description="Play a song from YouTube 🎵")
    @app_commands.describe(query="Song name or YouTube URL")
    async def play(self, ctx: commands.Context, *, query: str = None):
        if not query:
            embed = discord.Embed(title="🎵  Lumi Music — Commands", color=PINK)
            embed.add_field(name="▶️  Play",      value="`$play <song/URL>` — Play from YouTube\n`$search <query>` — Pick from 5 results", inline=False)
            embed.add_field(name="⏯️  Controls",  value="`$skip` / `$s` — Skip\n`$pause` / `$resume` — Toggle pause\n`$remove` — Remove last queued song\n`$remove <#>` — Remove by position", inline=False)
            embed.add_field(name="🎛️  Buttons",   value="⏮ Restart  🔁 Loop  ⏸ Pause  🔀 Shuffle  ⏭ Skip\n📋 Queue  ⏹ Stop", inline=False)
            embed.add_field(name="💡  Tips",      value="• Works with song names or YouTube URLs\n• Controls always appear at the bottom", inline=False)
            embed.set_footer(text="Example: $play never gonna give you up")
            return await ctx.send(embed=embed)

        if not ctx.author.voice:
            return await ctx.send(embed=discord.Embed(description="❌ Join a voice channel first!", color=discord.Color.red()), ephemeral=True)

        await ctx.typing()

        tracks = await wavelink.Playable.search(query)
        if not tracks:
            return await ctx.send(embed=discord.Embed(description="❌ Couldn't find that song!", color=discord.Color.red()))

        track = tracks[0]
        track.extras = wavelink.ExtrasNamespace({"requester": ctx.author.display_name})

        player: wavelink.Player = ctx.guild.voice_client  # type: ignore
        if not player:
            player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        elif player.channel != ctx.author.voice.channel:
            await player.move_to(ctx.author.voice.channel)

        if ctx.interaction is None:
            try: await ctx.message.delete()
            except Exception: pass

        if player.playing or player.paused:
            await player.queue.put_wait(track)
            pos = len(player.queue)
            embed = discord.Embed(title="📋  Added to Queue", color=PINK,
                description=f"**{track.title}**\n⏱ {format_duration(track.length)} · Position #{pos}")
            if track.artwork:
                embed.set_thumbnail(url=track.artwork)
            msg = await ctx.send(embed=embed)
            await self._move_np(player, ctx.channel)
            try: await msg.delete(delay=5)
            except Exception: pass
        else:
            await player.queue.put_wait(track)
            await player.play(player.queue.get())
            await self._send_np(player, ctx.channel)

    # ── $skip ─────────────────────────────────────────────────────

    @commands.command(name="skip", aliases=["s"])
    async def skip(self, ctx: commands.Context):
        player: wavelink.Player = ctx.guild.voice_client  # type: ignore
        if not player or not player.playing:
            return await ctx.send(embed=discord.Embed(description="❌ Nothing playing!", color=discord.Color.red()), delete_after=5)
        title = player.current.title
        await player.skip(force=True)
        await ctx.send(embed=discord.Embed(description=f"⏭ Skipped **{title}**", color=PINK), delete_after=5)
        try: await ctx.message.delete()
        except Exception: pass

    # ── $pause ────────────────────────────────────────────────────

    @commands.command(name="pause", aliases=["resume"])
    async def pause(self, ctx: commands.Context):
        player: wavelink.Player = ctx.guild.voice_client  # type: ignore
        if not player:
            return await ctx.send(embed=discord.Embed(description="❌ Nothing playing!", color=discord.Color.red()), delete_after=5)
        await player.pause(not player.paused)
        label = "⏸ Paused" if player.paused else "▶ Resumed"
        await ctx.send(embed=discord.Embed(description=f"{label} **{player.current.title}**", color=PINK), delete_after=5)
        try: await ctx.message.delete()
        except Exception: pass

    # ── $remove ───────────────────────────────────────────────────

    @commands.command(name="remove")
    async def remove(self, ctx: commands.Context, index: int = -1):
        player: wavelink.Player = ctx.guild.voice_client  # type: ignore
        if not player or player.queue.is_empty:
            return await ctx.send(embed=discord.Embed(description="❌ Queue is empty!", color=discord.Color.red()), delete_after=5)
        q = list(player.queue)
        target = len(q) - 1 if index == -1 else index - 1
        if target < 0 or target >= len(q):
            return await ctx.send(embed=discord.Embed(description=f"❌ Invalid position.", color=discord.Color.red()), delete_after=5)
        removed = q.pop(target)
        player.queue.clear()
        for t in q:
            await player.queue.put_wait(t)
        await ctx.send(embed=discord.Embed(description=f"🗑️ Removed **{removed.title}**", color=PINK), delete_after=5)
        try: await ctx.message.delete()
        except Exception: pass

    # ── $search ───────────────────────────────────────────────────

    @commands.command(name="search", aliases=["find"])
    async def search(self, ctx: commands.Context, *, query: str):
        if not ctx.author.voice:
            return await ctx.send(embed=discord.Embed(description="❌ Join a voice channel first!", color=discord.Color.red()), delete_after=5)
        try: await ctx.message.delete()
        except Exception: pass

        searching = await ctx.send(embed=discord.Embed(description=f"🔍 Searching for **{query}**...", color=PINK))
        tracks = await wavelink.Playable.search(query)
        if not tracks:
            return await searching.edit(embed=discord.Embed(description="❌ No results found!", color=discord.Color.red()))

        results = tracks[:5]
        lines   = [f"`{i}.` **{t.title[:60]}** · {format_duration(t.length)}" for i, t in enumerate(results, 1)]
        embed   = discord.Embed(title=f"🔍  Results for \"{query}\"", description="\n".join(lines), color=PINK)
        embed.set_footer(text="Select a song below • Expires in 30 seconds")
        await searching.edit(embed=embed, view=SearchView(self, results, ctx.author.display_name))


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
