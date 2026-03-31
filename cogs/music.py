import asyncio
import discord
from discord.ext import commands
import yt_dlp

from core.embeds import PINK

yt_dlp.utils.bug_reports_message = lambda: ''

FFMPEG_PATH = "/usr/bin/ffmpeg"

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'scsearch',
    'source_address': '0.0.0.0',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


# ── Utils ─────────────────────────────────────────────

def _fmt(seconds):
    if not seconds:
        return "Live"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02}"


# ── Audio Source ──────────────────────────────────────

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data):
        super().__init__(source, 1.0)

        self.data = data
        self.title = data.get('title', 'Unknown')
        self.url = data.get('url')

        self.webpage = data.get('webpage_url', '')
        self.duration = data.get('duration', 0)
        self.thumbnail = data.get('thumbnail')
        self.requester = None

    @classmethod
    async def from_url(cls, url, *, loop=None):
        loop = loop or asyncio.get_event_loop()

        data = await loop.run_in_executor(
            None, lambda: ytdl.extract_info(url, download=False)
        )

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url']

        return cls(
            discord.FFmpegPCMAudio(
                filename,
                executable=FFMPEG_PATH,
                before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                options="-vn -loglevel error"
            ),
            data=data
        )


# ── Queue ─────────────────────────────────────────────

class GuildQueue:
    def __init__(self):
        self.queue = []
        self.current = None


# ── Music Cog ─────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}

    def _get_q(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = GuildQueue()
        return self.queues[guild_id]

    # ── SAFE NEXT TRACK ────────────────────────────────

    async def _advance(self, ctx):
        q = self._get_q(ctx.guild.id)

        if not q.queue:
            q.current = None
            if ctx.voice_client:
                await ctx.voice_client.disconnect()
            return

        next_song = q.queue.pop(0)
        q.current = next_song

        ctx.voice_client.play(
            next_song,
            after=lambda e: self.bot.loop.call_soon_threadsafe(
                asyncio.create_task,
                self._advance(ctx)
            )
        )

        await ctx.send(embed=discord.Embed(
            description=f"🎶 Now playing: **{next_song.title}**",
            color=PINK
        ))

    # ── PLAY COMMAND ───────────────────────────────────

    @commands.hybrid_command(name="play")
    async def play(self, ctx, *, query: str):

        if not ctx.author.voice:
            return await ctx.send("❌ Join a voice channel first!")

        vc = ctx.voice_client
        if not vc:
            vc = await ctx.author.voice.channel.connect()

        await ctx.typing()

        try:
            if not query.startswith("http"):
                query = f"scsearch1:{query}"

            player = await YTDLSource.from_url(query, loop=self.bot.loop)
            player.requester = ctx.author.display_name

        except Exception as e:
            return await ctx.send(f"❌ Error: {e}")

        q = self._get_q(ctx.guild.id)

        # ── QUEUE HANDLING (FIXED) ──────────────────────

        if vc.is_playing() or vc.is_paused():
            q.queue.append(player)

            await ctx.send(embed=discord.Embed(
                description=f"📋 Added to queue: **{player.title}**",
                color=PINK
            ))

        else:
            q.current = player

            vc.play(
                player,
                after=lambda e: self.bot.loop.call_soon_threadsafe(
                    asyncio.create_task,
                    self._advance(ctx)
                )
            )

            await ctx.send(embed=discord.Embed(
                description=f"🎶 Now playing: **{player.title}**",
                color=PINK
            ))

    # ── SKIP ───────────────────────────────────────────

    @commands.command(name="skip")
    async def skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("⏭ Skipped")

    # ── STOP ───────────────────────────────────────────

    @commands.command(name="stop")
    async def stop(self, ctx):
        q = self._get_q(ctx.guild.id)
        q.queue.clear()
        q.current = None

        if ctx.voice_client:
            await ctx.voice_client.disconnect()

        await ctx.send("⏹ Stopped")

    # ── PAUSE ──────────────────────────────────────────

    @commands.command(name="pause")
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸ Paused")

    # ── RESUME ─────────────────────────────────────────

    @commands.command(name="resume")
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶ Resumed")


async def setup(bot):
    await bot.add_cog(Music(bot))