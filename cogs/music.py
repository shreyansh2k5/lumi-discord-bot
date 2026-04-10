import asyncio
import discord
from discord.ext import commands
import yt_dlp
import shutil
import os

from core.embeds import PINK

yt_dlp.utils.bug_reports_message = lambda: ''

# ───────────── FFmpeg Discovery ─────────────

def _find_ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    if os.path.isfile("/usr/bin/ffmpeg"):
        return "/usr/bin/ffmpeg"
    local = os.path.join(os.path.dirname(__file__), "..", "ffmpeg.exe")
    if os.path.isfile(local):
        return os.path.abspath(local)
    return "ffmpeg"

FFMPEG_PATH = _find_ffmpeg()
print(f"[Music] FFmpeg resolved to: {FFMPEG_PATH}")

FFMPEG_OPTS = {
    "executable":     FFMPEG_PATH,
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options":        "-vn -loglevel error",
}

# ───────────── yt-dlp setup ─────────────
#
# Two separate YoutubeDL instances:
#   YTDL_META  — fast, flat extraction. Used ONLY to get title/duration for
#                the "Added to queue" preview. Does NOT extract a stream URL.
#   YTDL_STREAM — full extraction. Called at the MOMENT of playback to get a
#                 fresh, never-expired CDN stream URL.
#
# Why two instances?
#   SoundCloud/YouTube CDN stream URLs are time-limited (typically 5–30 min).
#   If we extract the URL when the user queues song #3 and song #1+#2 each
#   take 4 minutes, the URL for song #3 is stale before FFmpeg ever touches
#   it → FFmpeg silently exits with code 0 → premature skip.

YTDL_META_OPTS = {
    'format':       'bestaudio/best',
    'noplaylist':   True,
    'quiet':        True,
    'no_warnings':  True,
    'default_search': 'scsearch',
    'source_address': '0.0.0.0',
    # extract_flat=True means "do NOT resolve the direct stream URL"
    # This makes the request ~3× faster for the queue preview.
    'extract_flat': 'in_playlist',
}

YTDL_STREAM_OPTS = {
    'format':       'bestaudio/best',
    'noplaylist':   True,
    'quiet':        True,
    'no_warnings':  True,
    'default_search': 'scsearch',
    'source_address': '0.0.0.0',
    # extractor_args tries tv_embedded client first, which is less restricted
    'extractor_args': {
        'youtube': {'player_client': ['tv_embedded', 'ios', 'web']}
    },
}

ytdl_meta   = yt_dlp.YoutubeDL(YTDL_META_OPTS)
ytdl_stream = yt_dlp.YoutubeDL(YTDL_STREAM_OPTS)


# ───────────── Utils ─────────────

def fmt_time(seconds):
    if not seconds:
        return "Live"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02}"


# ───────────── Async extraction helpers ─────────────

async def _fetch_meta(query: str, loop) -> dict:
    """
    Fast metadata fetch — returns {title, duration, webpage_url, thumbnail, query}.
    Does NOT return a playable stream URL (intentionally).
    """
    def _run():
        info = ytdl_meta.extract_info(query, download=False)
        if info and "entries" in info:
            info = info["entries"][0]
        if not info:
            raise ValueError("No results found.")
        return {
            "title":       info.get("title", "Unknown"),
            "duration":    info.get("duration", 0),
            "webpage_url": info.get("webpage_url") or info.get("url", ""),
            "thumbnail":   info.get("thumbnail", ""),
            # Store the original query so we can re-fetch later
            "query":       query,
        }
    return await loop.run_in_executor(None, _run)


async def _create_source(track: dict, loop) -> discord.PCMVolumeTransformer:
    """
    Called RIGHT BEFORE playback. Fetches a brand-new, never-expired stream
    URL and wraps it in an FFmpegPCMAudio source.

    We re-use the webpage_url if available (more precise), falling back to
    the original search query.
    """
    lookup = track.get("webpage_url") or track["query"]

    def _run():
        info = ytdl_stream.extract_info(lookup, download=False)
        if info and "entries" in info:
            info = info["entries"][0]
        if not info or not info.get("url"):
            raise ValueError(f"Could not extract stream for: {track['title']}")
        return info

    info = await loop.run_in_executor(None, _run)

    source = discord.FFmpegPCMAudio(info["url"], **FFMPEG_OPTS)
    player = discord.PCMVolumeTransformer(source, volume=1.0)

    # Attach metadata so the queue display stays correct
    player.title     = info.get("title",       track["title"])
    player.duration  = info.get("duration",    track["duration"])
    player.webpage   = info.get("webpage_url", track.get("webpage_url", ""))
    player.thumbnail = info.get("thumbnail",   track.get("thumbnail", ""))
    player.requester = track.get("requester", "Unknown")

    return player


# ───────────── Queue ─────────────

class GuildQueue:
    """
    Stores lightweight track dicts in the queue — NOT pre-fetched audio
    sources. Stream URLs are fetched fresh by _play_next() at playback time.

    Track dict shape:
        {
            "title":       str,
            "duration":    int,   # seconds
            "webpage_url": str,   # e.g. https://soundcloud.com/...
            "thumbnail":   str,
            "query":       str,   # original search string / URL
            "requester":   str,
        }
    """
    def __init__(self):
        self.queue   = []   # list[dict]
        self.current = None  # dict | None  (currently playing track metadata)


# ───────────── Music Cog ─────────────

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot    = bot
        self.queues = {}

    def get_queue(self, guild_id) -> GuildQueue:
        if guild_id not in self.queues:
            self.queues[guild_id] = GuildQueue()
        return self.queues[guild_id]

    # ── Scheduler (called from FFmpeg after= thread) ───────────────

    def _schedule_next(self, ctx):
        """
        Bridge between the non-async FFmpeg callback thread and the asyncio
        event loop. run_coroutine_threadsafe is the ONLY correct API here.
        """
        asyncio.run_coroutine_threadsafe(self._play_next(ctx), self.bot.loop)

    def _after_track(self, error, ctx):
        if error:
            print(f"[Music] FFmpeg error during playback: {error}")
        self._schedule_next(ctx)

    # ── Player engine ──────────────────────────────────────────────

    async def _play_next(self, ctx):
        """
        Pop the next track dict from the queue, fetch a FRESH stream URL
        right now, and start playback. Any pre-fetched URLs in the dict are
        intentionally ignored here — we always re-resolve just before playing.
        """
        queue = self.get_queue(ctx.guild.id)

        if not queue.queue:
            queue.current = None
            # Idle auto-disconnect after 5 minutes
            await asyncio.sleep(300)
            if ctx.voice_client and not ctx.voice_client.is_playing():
                try:
                    await ctx.voice_client.disconnect()
                except Exception:
                    pass
            return

        track = queue.queue.pop(0)
        queue.current = track

        if not ctx.voice_client or not ctx.voice_client.is_connected():
            print("[Music] Voice client gone before _play_next could play.")
            return

        # ── FRESH stream fetch ─────────────────────────────────────
        try:
            print(f"[Music] Fetching fresh stream for: {track['title']}")
            player = await _create_source(track, self.bot.loop)
        except Exception as exc:
            print(f"[Music] Stream fetch failed for '{track['title']}': {exc}")
            await ctx.send(embed=discord.Embed(
                description=f"⚠️ Skipped **{track['title']}** — could not load stream.\n`{exc}`",
                color=discord.Color.orange()
            ))
            # Try the next song instead of silently dying
            await self._play_next(ctx)
            return

        try:
            ctx.voice_client.play(
                player,
                after=lambda e: self._after_track(e, ctx),
            )
        except discord.ClientException as exc:
            print(f"[Music] vc.play() failed: {exc}")
            return

        await ctx.send(embed=discord.Embed(
            description=f"🎶 Now playing: **{player.title}** `[{fmt_time(player.duration)}]`\n"
                        f"👤 Requested by **{player.requester}**",
            color=PINK
        ))

    # ── Voice connection helper ────────────────────────────────────

    async def _connect(self, ctx) -> discord.VoiceClient | None:
        """
        Connect to voice and pin the channel to Singapore to avoid the
        Azure India → c-bom UDP-drop / 4006 bug.
        """
        channel = ctx.author.voice.channel

        if channel.rtc_region in (None, "india", "us-west", "us-east",
                                  "us-central", "us-south", "rotterdam",
                                  "russia", "sydney", "brazil", "hongkong",
                                  "southafrica", "japan", "europe"):
            try:
                await channel.edit(rtc_region="singapore")
                print(f"[Music] Overrode VC region → singapore (was {channel.rtc_region!r})")
            except discord.Forbidden:
                print("[Music] ⚠ No Manage Channels permission — cannot override VC region")
            except Exception as exc:
                print(f"[Music] Region edit failed: {exc}")

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

        if not query.startswith("http"):
            search_query = f"scsearch1:{query}"
        else:
            search_query = query

        # ── Fast metadata fetch (no stream URL yet) ──
        try:
            track = await _fetch_meta(search_query, self.bot.loop)
            track["requester"] = ctx.author.display_name
        except Exception as exc:
            return await ctx.send(f"❌ Could not find that song: {exc}")

        queue = self.get_queue(ctx.guild.id)

        if vc.is_playing() or vc.is_paused():
            # Add to queue — stream URL will be fetched when it's this song's turn
            queue.queue.append(track)
            await ctx.send(embed=discord.Embed(
                description=f"📋 Added to queue: **{track['title']}** `[{fmt_time(track['duration'])}]`\n"
                            f"Position: **#{len(queue.queue)}**",
                color=PINK
            ))
        else:
            # Play immediately — fetch fresh stream now
            queue.current = track
            try:
                player = await _create_source(track, self.bot.loop)
            except Exception as exc:
                queue.current = None
                return await ctx.send(f"❌ Failed to load stream: {exc}")

            vc.play(player, after=lambda e: self._after_track(e, ctx))
            await ctx.send(embed=discord.Embed(
                description=f"🎶 Now playing: **{player.title}** `[{fmt_time(player.duration)}]`\n"
                            f"👤 Requested by **{player.requester}**",
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
            lines.append(
                f"▶ **Now:** {queue.current['title']} "
                f"`[{fmt_time(queue.current.get('duration', 0))}]`"
            )
        for i, song in enumerate(queue.queue[:10], 1):
            lines.append(
                f"`{i}.` {song['title']} `[{fmt_time(song.get('duration', 0))}]`"
            )
        if len(queue.queue) > 10:
            lines.append(f"*…and {len(queue.queue) - 10} more*")

        await ctx.send(embed=discord.Embed(
            title="📋 Queue",
            description="\n".join(lines),
            color=PINK
        ))

    @commands.hybrid_command(name="nowplaying", aliases=["np"], description="Show current song")
    async def nowplaying(self, ctx):
        queue = self.get_queue(ctx.guild.id)
        if not queue.current:
            return await ctx.send("❌ Nothing is playing.")
        t = queue.current
        await ctx.send(embed=discord.Embed(
            title="🎵 Now Playing",
            description=f"**{t['title']}** `[{fmt_time(t.get('duration', 0))}]`\n"
                        f"👤 Requested by **{t.get('requester', 'Unknown')}**",
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

    # ── Region restore on disconnect ───────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if member.id != self.bot.user.id:
            return
        if before.channel and after.channel is None:
            try:
                await before.channel.edit(rtc_region=None)
                print(f"[Music] Restored VC region → auto for #{before.channel.name}")
            except Exception:
                pass


async def setup(bot):
    await bot.add_cog(Music(bot))