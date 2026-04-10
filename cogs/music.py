import asyncio
import discord
from discord.ext import commands
import yt_dlp
import subprocess
import shutil
import os

from core.embeds import PINK

yt_dlp.utils.bug_reports_message = lambda: ''

# ───────────── FFmpeg Discovery ─────────────
# Robustly locates FFmpeg so PM2's stripped PATH never causes a crash.
def _find_ffmpeg() -> str:
    # 1. Check PATH normally
    found = shutil.which("ffmpeg")
    if found:
        return found
    # 2. Hard-coded system path on Ubuntu/Debian
    if os.path.isfile("/usr/bin/ffmpeg"):
        return "/usr/bin/ffmpeg"
    # 3. Local Windows binary (dev machine)
    local = os.path.join(os.path.dirname(__file__), "..", "ffmpeg.exe")
    if os.path.isfile(local):
        return os.path.abspath(local)
    return "ffmpeg"  # last resort – will raise FileNotFoundError clearly

FFMPEG_PATH = _find_ffmpeg()
print(f"[Music] FFmpeg resolved to: {FFMPEG_PATH}")

FFMPEG_OPTS = {
    "executable":     FFMPEG_PATH,
    # -reconnect flags keep yt-dlp streams alive if the CDN hiccups
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options":        "-vn -loglevel error",
}

YTDL_OPTIONS = {
    'format':         'bestaudio/best',
    'noplaylist':     True,
    'quiet':          True,
    'no_warnings':    True,
    # scsearch bypasses Azure-flagged YouTube IPs via SoundCloud
    'default_search': 'scsearch',
    'source_address': '0.0.0.0',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


# ───────────── Utils ─────────────

def fmt_time(seconds):
    if not seconds:
        return "Live"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02}"


# ───────────── Audio Source ─────────────

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data):
        super().__init__(source, volume=1.0)
        self.title     = data.get("title", "Unknown")
        self.url       = data.get("url")
        self.duration  = data.get("duration", 0)
        self.webpage   = data.get("webpage_url", "")
        self.thumbnail = data.get("thumbnail")
        self.requester = None

    @classmethod
    async def from_url(cls, url, *, loop):
        data = await loop.run_in_executor(
            None, lambda: ytdl.extract_info(url, download=False)
        )
        if "entries" in data:
            data = data["entries"][0]

        return cls(
            discord.FFmpegPCMAudio(data["url"], **FFMPEG_OPTS),
            data=data,
        )


# ───────────── Queue ─────────────

class GuildQueue:
    def __init__(self):
        self.queue   = []
        self.current = None


# ───────────── Music Cog ─────────────

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot    = bot
        self.queues = {}

    def get_queue(self, guild_id) -> GuildQueue:
        if guild_id not in self.queues:
            self.queues[guild_id] = GuildQueue()
        return self.queues[guild_id]

    # ── Internal helpers ──────────────────────────────────────────

    def _schedule_next(self, ctx):
        """
        Called from the FFmpeg after= callback (non-async thread).
        Schedules _play_next as a proper coroutine-task on the event loop.
        Using asyncio.run_coroutine_threadsafe is the correct pattern here —
        it receives a coroutine, NOT asyncio.create_task.
        """
        asyncio.run_coroutine_threadsafe(self._play_next(ctx), self.bot.loop)

    async def _play_next(self, ctx):
        """Async engine that pops the queue and starts the next track."""
        queue = self.get_queue(ctx.guild.id)

        if not queue.queue:
            queue.current = None
            # Disconnect after a short idle grace period
            await asyncio.sleep(300)
            if ctx.voice_client and not ctx.voice_client.is_playing():
                await ctx.voice_client.disconnect()
            return

        next_song = queue.queue.pop(0)
        queue.current = next_song

        # Guard: voice client might have disconnected (e.g. 4006 kick)
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            return

        try:
            ctx.voice_client.play(
                next_song,
                after=lambda e: self._log_error_and_schedule(e, ctx),
            )
        except discord.ClientException as exc:
            # Already playing — this should not happen but guard anyway
            print(f"[Music] play() failed: {exc}")
            return

        await ctx.send(embed=discord.Embed(
            description=f"🎶 Now playing: **{next_song.title}**",
            color=PINK
        ))

    def _log_error_and_schedule(self, error, ctx):
        """after= callback: log FFmpeg errors then schedule the next track."""
        if error:
            print(f"[Music] Playback error: {error}")
        self._schedule_next(ctx)

    # ── Voice connection helper ────────────────────────────────────

    async def _connect(self, ctx) -> discord.VoiceClient | None:
        """
        Connects to the user's voice channel.

        Azure India datacenter bug: Discord's automatic server selection
        routes Indian VCs to c-bom11.discord.media which drops UDP audio
        packets → 4006 disconnect after ~30 s of silence.

        FIX: Override rtc_region to 'singapore' on connect.
        Singapore (sgp) is the next closest stable region to India and
        does NOT have the UDP-drop bug.

        We do this programmatically so users don't have to touch server
        settings. The channel's region is reset to auto when the bot
        disconnects (see on_voice_state_update).
        """
        channel = ctx.author.voice.channel

        # Only override if currently on auto or India
        needs_override = channel.rtc_region in (None, "india")

        if needs_override:
            try:
                await channel.edit(rtc_region="singapore")
                print(f"[Music] Overrode VC region → singapore (was {channel.rtc_region!r})")
            except discord.Forbidden:
                print("[Music] ⚠ No permission to edit VC region — bot may hit 4006")
            except Exception as e:
                print(f"[Music] Region edit failed: {e}")

        vc = ctx.voice_client
        if not vc:
            vc = await channel.connect()
        elif vc.channel != channel:
            await vc.move_to(channel)

        return vc

    # ── Commands ──────────────────────────────────────────────────

    @commands.hybrid_command(name="play", description="Play a song or search SoundCloud")
    async def play(self, ctx, *, query: str):
        if not ctx.author.voice:
            return await ctx.send("❌ Join a voice channel first.")

        vc = await self._connect(ctx)
        if not vc:
            return await ctx.send("❌ Could not connect to your voice channel.")

        await ctx.typing()

        try:
            if not query.startswith("http"):
                query = f"scsearch1:{query}"

            player = await YTDLSource.from_url(query, loop=self.bot.loop)
            player.requester = ctx.author.display_name

        except Exception as e:
            return await ctx.send(f"❌ Error: {e}")

        queue = self.get_queue(ctx.guild.id)

        if vc.is_playing() or vc.is_paused():
            queue.queue.append(player)
            await ctx.send(embed=discord.Embed(
                description=f"📋 Added to queue: **{player.title}**",
                color=PINK
            ))
        else:
            queue.current = player
            vc.play(
                player,
                after=lambda e: self._log_error_and_schedule(e, ctx),
            )
            await ctx.send(embed=discord.Embed(
                description=f"🎶 Now playing: **{player.title}**",
                color=PINK
            ))

    @commands.hybrid_command(name="skip", description="Skip the current song")
    async def skip(self, ctx):
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            ctx.voice_client.stop()
            await ctx.send("⏭ Skipped.")
        else:
            await ctx.send("❌ Nothing is playing.")

    @commands.hybrid_command(name="pause", description="Pause playback")
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸ Paused.")
        else:
            await ctx.send("❌ Nothing is playing.")

    @commands.hybrid_command(name="resume", description="Resume playback")
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶ Resumed.")
        else:
            await ctx.send("❌ Nothing is paused.")

    @commands.hybrid_command(name="queue", description="Show the current queue")
    async def queue_cmd(self, ctx):
        queue = self.get_queue(ctx.guild.id)
        if not queue.queue and not queue.current:
            return await ctx.send("📋 Queue is empty.")

        lines = []
        if queue.current:
            lines.append(f"**Now:** {queue.current.title} `[{fmt_time(queue.current.duration)}]`")
        for i, song in enumerate(queue.queue[:10], 1):
            lines.append(f"`{i}.` {song.title} `[{fmt_time(song.duration)}]`")
        if len(queue.queue) > 10:
            lines.append(f"*…and {len(queue.queue) - 10} more*")

        await ctx.send(embed=discord.Embed(
            title="📋 Queue",
            description="\n".join(lines),
            color=PINK
        ))

    @commands.hybrid_command(name="stop", description="Stop playback and disconnect")
    async def stop(self, ctx):
        queue = self.get_queue(ctx.guild.id)
        queue.queue.clear()
        queue.current = None

        if ctx.voice_client:
            await ctx.voice_client.disconnect()

        await ctx.send("⏹ Stopped and disconnected.")

    @commands.hybrid_command(name="volume", description="Set volume (10–200)")
    async def volume(self, ctx, vol: int):
        if not ctx.voice_client or not ctx.voice_client.source:
            return await ctx.send("❌ Nothing is playing.")
        vol = max(10, min(200, vol))
        ctx.voice_client.source.volume = vol / 100
        await ctx.send(f"🔊 Volume set to **{vol}%**")

    # ── Region reset on disconnect ─────────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """
        When the bot disconnects from a VC, restore rtc_region → None (auto)
        so the manual server settings are not permanently changed.
        """
        if member.id != self.bot.user.id:
            return
        if before.channel and after.channel is None:
            try:
                await before.channel.edit(rtc_region=None)
                print(f"[Music] Restored VC region → auto for #{before.channel.name}")
            except Exception:
                pass  # non-critical


async def setup(bot):
    await bot.add_cog(Music(bot))