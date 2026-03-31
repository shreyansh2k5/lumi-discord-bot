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

        self.title = data.get("title", "Unknown")
        self.url = data.get("url")
        self.duration = data.get("duration", 0)
        self.webpage = data.get("webpage_url", "")
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
            discord.FFmpegPCMAudio(
                data["url"],
                executable=FFMPEG_PATH,
                before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                options="-vn -loglevel error",
            ),
            data=data,
        )


# ───────────── Queue ─────────────

class GuildQueue:
    def __init__(self):
        self.queue = []
        self.current = None


# ───────────── Music Cog ─────────────

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = GuildQueue()
        return self.queues[guild_id]

    # ───────────── Player Engine ─────────────

    async def play_next(self, ctx):
        queue = self.get_queue(ctx.guild.id)

        if not queue.queue:
            queue.current = None
            if ctx.voice_client:
                await ctx.voice_client.disconnect()
            return

        next_song = queue.queue.pop(0)
        queue.current = next_song

        ctx.voice_client.play(
            next_song,
            after=lambda e: self.bot.loop.call_soon_threadsafe(
                asyncio.create_task,
                self.play_next(ctx),
            ),
        )

        await ctx.send(embed=discord.Embed(
            description=f"🎶 Now playing: **{next_song.title}**",
            color=PINK
        ))

    # ───────────── Commands ─────────────

    @commands.hybrid_command(name="play")
    async def play(self, ctx, *, query: str):

        if not ctx.author.voice:
            return await ctx.send("❌ Join a voice channel first")

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
                after=lambda e: self.bot.loop.call_soon_threadsafe(
                    asyncio.create_task,
                    self.play_next(ctx),
                ),
            )

            await ctx.send(embed=discord.Embed(
                description=f"🎶 Now playing: **{player.title}**",
                color=PINK
            ))

    @commands.command(name="skip")
    async def skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("⏭ Skipped")

    @commands.command(name="pause")
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸ Paused")

    @commands.command(name="resume")
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶ Resumed")

    @commands.command(name="stop")
    async def stop(self, ctx):
        queue = self.get_queue(ctx.guild.id)
        queue.queue.clear()
        queue.current = None

        if ctx.voice_client:
            await ctx.voice_client.disconnect()

        await ctx.send("⏹ Stopped")


async def setup(bot):
    await bot.add_cog(Music(bot))