# cogs/music.py
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp

from core.embeds import PINK

yt_dlp.utils.bug_reports_message = lambda: ''

YTDL_OPTIONS = {
    'format':            'bestaudio/best',
    'noplaylist':        True,
    'nocheckcertificate': True,
    'ignoreerrors':      False,
    'quiet':             True,
    'no_warnings':       True,
    'default_search':    'scsearch',
    'source_address':    '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options':        '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


def _fmt(seconds: int) -> str:
    if not seconds: return "Live"
    h, rem = divmod(int(seconds), 3600)
    m, s   = divmod(rem, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


# ── Audio source ──────────────────────────────────────────────────

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=1.0):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        
        # This extract_info call must be clean of 'before' arguments
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a search result
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)

    @classmethod
    async def search_many(cls, query: str, limit: int = 5, *, loop=None) -> list[dict]:
        loop = loop or asyncio.get_event_loop()
        opts = {**YTDL_OPTIONS, 'extract_flat': True}
        def _search():
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"scsearch{limit}:{query}", download=False)
                return [
                    {
                        'title':    e.get('title', 'Unknown'),
                        'url':      e.get('url') or e.get('webpage_url', ''),
                        'duration': e.get('duration', 0),
                        'uploader': e.get('uploader') or e.get('channel', 'Unknown'),
                    }
                    for e in info.get('entries', [])[:limit]
                ]
        return await loop.run_in_executor(None, _search)


# ── Per-guild queue ───────────────────────────────────────────────

class GuildQueue:
    def __init__(self):
        self.queue:   list[YTDLSource] = []
        self.current: YTDLSource | None = None
        self.np_msg:  discord.Message | None = None
        self.loop:    bool = False


# ── Now-playing embed ─────────────────────────────────────────────

def _np_embed(src: YTDLSource, queue_len: int, paused: bool, loop: bool) -> discord.Embed:
    embed = discord.Embed(
        title="🎵  Now Playing",
        description=f"**[{src.title}]({src.webpage})**",
        color=PINK)
    embed.add_field(name="⏱ Duration",  value=_fmt(src.duration), inline=True)
    embed.add_field(name="👤 Requester", value=src.requester or "Unknown", inline=True)
    status = []
    if paused: status.append("⏸ Paused")
    if loop:   status.append("🔁 Loop")
    status.append(f"📋 Queue: {queue_len}")
    embed.add_field(name="Status", value=" · ".join(status), inline=False)
    if src.thumbnail:
        embed.set_thumbnail(url=src.thumbnail)
    embed.set_footer(text="Lumi Music 🎶  •  Use the buttons to control")
    return embed


# ── Control buttons ───────────────────────────────────────────────

class MusicView(discord.ui.View):
    def __init__(self, cog: 'Music', guild_id: int):
        super().__init__(timeout=None)
        self.cog = cog; self.guild_id = guild_id

    def _q(self) -> GuildQueue | None:
        return self.cog.queues.get(self.guild_id)

    def _vc(self) -> discord.VoiceClient | None:
        guild = self.cog.bot.get_guild(self.guild_id)
        return guild.voice_client if guild else None

    async def _refresh(self, interaction: discord.Interaction):
        q  = self._q(); vc = self._vc()
        if q and q.current:
            paused = vc.is_paused() if vc else False
            embed  = _np_embed(q.current, len(q.queue), paused, q.loop)
            try: await interaction.response.edit_message(embed=embed, view=self)
            except Exception: await interaction.response.defer()
        else:
            try:
                await interaction.response.edit_message(
                    embed=discord.Embed(description="⏹ Stopped.", color=PINK), view=None)
            except Exception: await interaction.response.defer()

    @discord.ui.button(emoji="⏮", style=discord.ButtonStyle.secondary, row=0)
    async def btn_prev(self, i: discord.Interaction, b: discord.ui.Button):
        q = self._q(); vc = self._vc()
        if not q or not q.current or not vc:
            return await i.response.send_message("Nothing playing!", ephemeral=True)
        # Re-insert current at front so it replays
        q.queue.insert(0, q.current)
        q.queue.insert(0, q.current)
        vc.stop()
        await i.response.defer()

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=0)
    async def btn_loop(self, i: discord.Interaction, b: discord.ui.Button):
        q = self._q()
        if not q: return await i.response.send_message("Nothing playing!", ephemeral=True)
        q.loop = not q.loop
        b.style = discord.ButtonStyle.success if q.loop else discord.ButtonStyle.secondary
        await self._refresh(i)

    @discord.ui.button(emoji="⏸", style=discord.ButtonStyle.primary, row=0)
    async def btn_pause(self, i: discord.Interaction, b: discord.ui.Button):
        vc = self._vc()
        if not vc: return await i.response.send_message("Nothing playing!", ephemeral=True)
        if vc.is_playing():   vc.pause();  b.emoji = discord.PartialEmoji(name="▶"); b.style = discord.ButtonStyle.secondary
        elif vc.is_paused():  vc.resume(); b.emoji = discord.PartialEmoji(name="⏸"); b.style = discord.ButtonStyle.primary
        await self._refresh(i)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, row=0)
    async def btn_shuffle(self, i: discord.Interaction, b: discord.ui.Button):
        q = self._q()
        if not q: return await i.response.send_message("Nothing playing!", ephemeral=True)
        import random; random.shuffle(q.queue)
        await i.response.defer()

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.secondary, row=0)
    async def btn_skip(self, i: discord.Interaction, b: discord.ui.Button):
        vc = self._vc()
        if not vc or not vc.is_playing():
            return await i.response.send_message("Nothing to skip!", ephemeral=True)
        vc.stop()
        await i.response.defer()

    @discord.ui.button(emoji="📋", style=discord.ButtonStyle.secondary, row=1)
    async def btn_queue(self, i: discord.Interaction, b: discord.ui.Button):
        q = self._q()
        if not q or not q.queue:
            return await i.response.send_message("Queue is empty!", ephemeral=True)
        lines = [f"`{n}.` {s.title} ({_fmt(s.duration)})"
                 for n, s in enumerate(q.queue[:10], 1)]
        if len(q.queue) > 10: lines.append(f"*...and {len(q.queue)-10} more*")
        await i.response.send_message(
            embed=discord.Embed(title="📋  Queue", description="\n".join(lines), color=PINK),
            ephemeral=True)

    @discord.ui.button(emoji="🔉", style=discord.ButtonStyle.secondary, row=1)
    async def btn_vdn(self, i: discord.Interaction, b: discord.ui.Button):
        vc = self._vc()
        if not vc or not vc.source: return await i.response.send_message("Nothing playing!", ephemeral=True)
        if isinstance(vc.source, discord.PCMVolumeTransformer):
            vc.source.volume = max(0.1, vc.source.volume - 0.1)
        await self._refresh(i)

    @discord.ui.button(emoji="⏹", style=discord.ButtonStyle.danger, row=1)
    async def btn_stop(self, i: discord.Interaction, b: discord.ui.Button):
        q = self._q(); vc = self._vc()
        if not vc: return await i.response.send_message("Nothing playing!", ephemeral=True)
        if q: q.queue.clear(); q.current = None; q.np_msg = None
        await vc.disconnect()
        try:
            await i.response.edit_message(
                embed=discord.Embed(description="⏹ Stopped and disconnected.", color=PINK), view=None)
        except Exception: await i.response.defer()

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, row=1)
    async def btn_vup(self, i: discord.Interaction, b: discord.ui.Button):
        vc = self._vc()
        if not vc or not vc.source: return await i.response.send_message("Nothing playing!", ephemeral=True)
        if isinstance(vc.source, discord.PCMVolumeTransformer):
            vc.source.volume = min(2.0, vc.source.volume + 0.1)
        await self._refresh(i)


# ── Search dropdown ───────────────────────────────────────────────

class SearchSelect(discord.ui.Select):
    def __init__(self, cog: 'Music', results: list[dict], requester: str):
        self.cog = cog; self.results = results; self.requester = requester
        options = [
            discord.SelectOption(
                label=r['title'][:100],
                description=f"{_fmt(r.get('duration',0))} · {r.get('uploader','')[:40]}"[:100],
                value=str(i))
            for i, r in enumerate(results)
        ]
        super().__init__(placeholder="🎵 Pick a song...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        chosen = self.results[int(self.values[0])]
        await interaction.message.edit(
            embed=discord.Embed(description=f"⏳ Loading **{chosen['title']}**...", color=PINK), view=None)
        try:
            src = await YTDLSource.from_query(chosen['url'], loop=self.cog.bot.loop)
        except Exception as e:
            return await interaction.followup.send(f"❌ Failed: {e}", ephemeral=True)
        src.requester = self.requester
        if not interaction.user.voice:
            return await interaction.followup.send("Join a voice channel first!", ephemeral=True)
        await self.cog._queue_or_play(
            interaction.guild, interaction.user.voice.channel, interaction.channel, src)
        await interaction.message.edit(
            embed=discord.Embed(description=f"✅ **{src.title}** added!", color=PINK))


class SearchView(discord.ui.View):
    def __init__(self, cog, results, requester):
        super().__init__(timeout=30)
        self.add_item(SearchSelect(cog, results, requester))


# ── Music Cog ─────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot    = bot
        self.queues: dict[int, GuildQueue] = {}

    def _get_q(self, guild_id: int) -> GuildQueue:
        if guild_id not in self.queues:
            self.queues[guild_id] = GuildQueue()
        return self.queues[guild_id]

    def _play_next(self, ctx: commands.Context):
        """Sync callback — schedules next track via run_coroutine_threadsafe."""
        asyncio.run_coroutine_threadsafe(
            self._advance(ctx), self.bot.loop)

    async def _advance(self, ctx: commands.Context):
        q = self._get_q(ctx.guild.id)
        if q.loop and q.current:
            q.queue.insert(0, q.current)
        if not q.queue:
            q.current = None
            if q.np_msg:
                try: await q.np_msg.edit(
                    embed=discord.Embed(description="✅ Queue finished!", color=PINK), view=None)
                except Exception: pass
            if ctx.voice_client:
                try: await ctx.voice_client.disconnect()
                except Exception: pass
            return
        src = q.queue.pop(0)
        q.current = src
        ctx.voice_client.play(src, after=lambda e: self._play_next(ctx))
        await self._send_np(ctx.guild.id, src, ctx.channel)

    async def _send_np(self, guild_id: int, src: YTDLSource, channel: discord.TextChannel):
        q = self._get_q(guild_id)
        vc = channel.guild.voice_client
        paused = vc.is_paused() if vc else False
        if q.np_msg:
            try: await q.np_msg.delete()
            except Exception: pass
        embed = _np_embed(src, len(q.queue), paused, q.loop)
        view  = MusicView(self, guild_id)
        q.np_msg = await channel.send(embed=embed, view=view)

    async def _queue_or_play(self, guild, vc_channel, channel, src: YTDLSource):
        vc = guild.voice_client
        if not vc:
            vc = await vc_channel.connect()
        elif vc.channel != vc_channel:
            await vc.move_to(vc_channel)

        q = self._get_q(guild.id)
        if vc.is_playing() or vc.is_paused():
            q.queue.append(src)
            pos   = len(q.queue)
            embed = discord.Embed(
                title="📋  Added to Queue",
                description=f"**{src.title}**\n⏱ {_fmt(src.duration)} · Position #{pos}",
                color=PINK)
            if src.thumbnail: embed.set_thumbnail(url=src.thumbnail)
            msg = await channel.send(embed=embed)
            await self._send_np(guild.id, q.current, channel)
            try: await msg.delete(delay=5)
            except Exception: pass
        else:
            q.current = src
            # Create a fake ctx-like object for _play_next callback
            class _Ctx:
                def __init__(self, g, vc_, loop): self.guild=g; self.voice_client=vc_; self.loop=loop
            fake_ctx = _Ctx(guild, vc, self.bot.loop)
            vc.play(src, after=lambda e: self._play_next(fake_ctx))
            await self._send_np(guild.id, src, channel)

    # ── Commands ──────────────────────────────────────────────────

    @commands.hybrid_command(name="play", description="Play a song from SoundCloud")
    async def play(self, ctx, *, query: str):
        if not ctx.author.voice:
            return await ctx.send("❌ You need to join a voice channel first!", ephemeral=True)

        voice_client = ctx.voice_client
        if not voice_client:
            voice_client = await ctx.author.voice.channel.connect()

        await ctx.typing()

        try:
            # Check if we need to search or if it's a direct URL
            if not query.startswith("http"):
                search_query = f"scsearch1:{query}" # Force only 1 result from SoundCloud
            else:
                search_query = query

            player = await YTDLSource.from_url(search_query, loop=self.bot.loop, stream=True)
        except Exception as e:
            return await ctx.send(f"❌ An error occurred during playback: {e}")

        m_queue = self.get_queue(ctx.guild.id)
        
        if voice_client.is_playing() or voice_client.is_paused():
            m_queue.queue.append({'player': player, 'title': player.title})
            await ctx.send(embed=discord.Embed(
                description=f"📋 Added to queue: **{player.title}**", 
                color=self.PINK))
        else:
            m_queue.current = {'player': player, 'title': player.title}
            voice_client.play(player, after=lambda e: self.play_next(ctx))
            await ctx.send(embed=discord.Embed(
                description=f"🎶 Now playing: **{player.title}**", 
                color=self.PINK))

    @commands.command(name="skip", aliases=["s"])
    async def skip(self, ctx: commands.Context):
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send(embed=discord.Embed(
                description="❌ Nothing playing!", color=discord.Color.red()), delete_after=5)
        ctx.voice_client.stop()
        await ctx.send(embed=discord.Embed(description="⏭ Skipped!", color=PINK), delete_after=5)
        try: await ctx.message.delete()
        except Exception: pass

    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send(embed=discord.Embed(description="⏸ Paused.", color=PINK), delete_after=5)
        try: await ctx.message.delete()
        except Exception: pass

    @commands.command(name="resume")
    async def resume(self, ctx: commands.Context):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send(embed=discord.Embed(description="▶ Resumed.", color=PINK), delete_after=5)
        try: await ctx.message.delete()
        except Exception: pass

    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context):
        q = self._get_q(ctx.guild.id)
        q.queue.clear(); q.current = None; q.np_msg = None
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        await ctx.send(embed=discord.Embed(description="⏹ Stopped and cleared queue.", color=PINK), delete_after=5)
        try: await ctx.message.delete()
        except Exception: pass

    @commands.command(name="remove")
    async def remove(self, ctx: commands.Context, index: int = -1):
        q = self._get_q(ctx.guild.id)
        if not q.queue:
            return await ctx.send(embed=discord.Embed(
                description="❌ Queue is empty!", color=discord.Color.red()), delete_after=5)
        target = len(q.queue) - 1 if index == -1 else index - 1
        if target < 0 or target >= len(q.queue):
            return await ctx.send(embed=discord.Embed(
                description=f"❌ Invalid. Queue has {len(q.queue)} song(s).", color=discord.Color.red()), delete_after=5)
        removed = q.queue.pop(target)
        await ctx.send(embed=discord.Embed(
            description=f"🗑️ Removed **{removed.title}**", color=PINK), delete_after=5)
        try: await ctx.message.delete()
        except Exception: pass

    @commands.command(name="search", aliases=["find"])
    async def search(self, ctx: commands.Context, *, query: str):
        if not ctx.author.voice:
            return await ctx.send(embed=discord.Embed(
                description="❌ Join a voice channel first!", color=discord.Color.red()), delete_after=5)
        try: await ctx.message.delete()
        except Exception: pass
        msg     = await ctx.send(embed=discord.Embed(description=f"🔍 Searching **{query}**...", color=PINK))
        results = await YTDLSource.search_many(query, 5, loop=self.bot.loop)
        if not results:
            return await msg.edit(embed=discord.Embed(description="❌ No results found.", color=discord.Color.red()))
        lines = [f"`{i}.` **{r['title'][:60]}** · {_fmt(r.get('duration',0))}"
                 for i, r in enumerate(results, 1)]
        embed = discord.Embed(title=f"🔍  \"{query}\"", description="\n".join(lines), color=PINK)
        embed.set_footer(text="Pick a song below • 30s to choose")
        await msg.edit(embed=embed, view=SearchView(self, results, ctx.author.display_name))


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))