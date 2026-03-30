import asyncio
import discord
from discord.ext import commands
import yt_dlp

# Suppress noise about console usage from errors
yt_dlp.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'scsearch',  # Forces text searches to use SoundCloud!
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=1.0):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # Take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class MusicQueue:
    def __init__(self):
        self.queue = []
        self.current = None


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.music_queues = {}
        self.PINK = discord.Color.from_rgb(255, 105, 180) # Adjust to your exact PINK

    def get_queue(self, guild_id):
        if guild_id not in self.music_queues:
            self.music_queues[guild_id] = MusicQueue()
        return self.music_queues[guild_id]

    def play_next(self, ctx):
        m_queue = self.get_queue(ctx.guild.id)
        if len(m_queue.queue) > 0:
            m_queue.current = m_queue.queue.pop(0)
            ctx.voice_client.play(m_queue.current['player'], after=lambda e: self.play_next(ctx))
            
            # Use asyncio.run_coroutine_threadsafe to send messages from a sync callback
            coro = ctx.send(embed=discord.Embed(
                description=f"🎶 Now playing: **{m_queue.current['title']}**", 
                color=self.PINK))
            asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
        else:
            m_queue.current = None
            coro = ctx.voice_client.disconnect()
            asyncio.run_coroutine_threadsafe(coro, self.bot.loop)

    @commands.hybrid_command(name="play", description="Play a song from SoundCloud")
    async def play(self, ctx, *, query: str):
        if not ctx.author.voice:
            return await ctx.send("❌ You need to join a voice channel first!", ephemeral=True)

        voice_client = ctx.voice_client
        if not voice_client:
            voice_client = await ctx.author.voice.channel.connect()

        await ctx.typing()

        try:
            player = await YTDLSource.from_url(query, loop=self.bot.loop, stream=True)
        except Exception as e:
            return await ctx.send(f"❌ An error occurred: {e}")

        m_queue = self.get_queue(ctx.guild.id)
        
        if voice_client.is_playing() or voice_client.is_paused():
            m_queue.queue.append({'player': player, 'title': player.title})
            await ctx.send(embed=discord.Embed(
                description=f"📋 Added to queue: **{player.title}**\nPosition: {len(m_queue.queue)}", 
                color=self.PINK))
        else:
            m_queue.current = {'player': player, 'title': player.title}
            voice_client.play(player, after=lambda e: self.play_next(ctx))
            await ctx.send(embed=discord.Embed(
                description=f"🎶 Now playing: **{player.title}**", 
                color=self.PINK))

    @commands.hybrid_command(name="skip", description="Skips the current song")
    async def skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop() # Triggers the 'after' callback to play next
            await ctx.send("⏭️ Skipped!")
        else:
            await ctx.send("❌ Nothing is playing right now.", ephemeral=True)

    @commands.hybrid_command(name="pause", description="Pauses the music")
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸️ Paused.")
        else:
            await ctx.send("❌ Nothing is playing right now.", ephemeral=True)

    @commands.hybrid_command(name="resume", description="Resumes the music")
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶️ Resumed.")
        else:
            await ctx.send("❌ Music is not paused.", ephemeral=True)

    @commands.hybrid_command(name="stop", description="Stops the music and clears the queue")
    async def stop(self, ctx):
        m_queue = self.get_queue(ctx.guild.id)
        m_queue.queue.clear()
        
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("⏹️ Disconnected and cleared the queue.")
        else:
            await ctx.send("❌ I'm not in a voice channel.", ephemeral=True)

    @commands.hybrid_command(name="queue", description="Shows the current music queue")
    async def queue(self, ctx):
        m_queue = self.get_queue(ctx.guild.id)
        
        if not m_queue.queue and not m_queue.current:
            return await ctx.send("The queue is empty.", ephemeral=True)
            
        embed = discord.Embed(title="📋 Current Queue", color=self.PINK)
        
        if m_queue.current:
            embed.add_field(name="Now Playing", value=m_queue.current['title'], inline=False)
            
        if m_queue.queue:
            queue_list = "\n".join([f"`{i+1}.` {song['title']}" for i, song in enumerate(m_queue.queue[:10])])
            if len(m_queue.queue) > 10:
                queue_list += f"\n*...and {len(m_queue.queue) - 10} more*"
            embed.add_field(name="Up Next", value=queue_list, inline=False)
            
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Music(bot))