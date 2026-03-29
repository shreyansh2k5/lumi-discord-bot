# cogs/music.py
import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from music.ytdl   import fetch_track, search_tracks, format_duration
from music.player import get_player, create_player, remove_player, GuildPlayer
from music.embeds import build_np_embed
from music.views  import MusicControlView, SearchView
from core.embeds  import PINK


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Internal ─────────────────────────────────────────────────

    def _after(self, guild_id: int, channel):
        asyncio.run_coroutine_threadsafe(self._advance(guild_id, channel), self.bot.loop)

    async def _advance(self, guild_id: int, channel):
        p = get_player(guild_id)
        if not p: return
        if not p.queue and not p.loop:
            p.current = None
            if p.np_msg:
                try: await p.np_msg.edit(
                    embed=discord.Embed(description="✅ Queue finished!", color=PINK), view=None)
                except Exception: pass
            guild = self.bot.get_guild(guild_id)
            if guild and guild.voice_client:
                try: await guild.voice_client.disconnect()
                except Exception: pass
            remove_player(guild_id)
            return
        p.play_next(after=lambda e: self._after(guild_id, channel))
        await self._send_np(p, channel)

    async def _send_np(self, p: GuildPlayer, channel):
        """Delete old now-playing and send a fresh one at the bottom."""
        if p.np_msg:
            try: await p.np_msg.delete()
            except Exception: pass
        guild_id = p.vc.guild.id
        embed = build_np_embed(p.current, len(p.queue), p.paused, p.loop, p.volume_pct)
        view  = MusicControlView(self, guild_id)
        p.np_msg = await channel.send(embed=embed, view=view)

    async def _queue_or_play(self, guild, vc_channel, text_channel, track: dict):
        """Shared logic for $play and search select — join VC and queue/play."""
        guild_id = guild.id
        p = get_player(guild_id)

        if p:
            if p.vc.channel != vc_channel:
                await p.vc.move_to(vc_channel)
        else:
            vc = await vc_channel.connect()
            p  = create_player(guild_id, vc)

        if p.playing or p.paused:
            p.queue.append(track)
            pos   = len(p.queue)
            embed = discord.Embed(
                title="📋  Added to Queue",
                description=f"**{track['title']}**\n⏱ {format_duration(track.get('duration',0))} · Position #{pos}",
                color=PINK)
            if track.get("thumbnail"): embed.set_thumbnail(url=track["thumbnail"])
            msg = await text_channel.send(embed=embed)
            # Move now-playing controls to bottom
            await self._send_np(p, text_channel)
            try: await msg.delete(delay=5)
            except Exception: pass
        else:
            p.queue.append(track)
            p.play_next(after=lambda e: self._after(guild_id, text_channel))
            await self._send_np(p, text_channel)

    # ── Commands ─────────────────────────────────────────────────

    @commands.hybrid_command(name="play", description="Play a song from YouTube 🎵")
    @app_commands.describe(query="Song name or YouTube URL")
    async def play(self, ctx: commands.Context, *, query: str = None):
        if not query:
            embed = discord.Embed(title="🎵  Lumi Music — Commands", color=PINK)
            embed.add_field(name="▶️  Play",     value="`$play <song/URL>`\n`$search <query>`",   inline=False)
            embed.add_field(name="⏯️  Controls", value="`$skip` `$pause` `$resume` `$remove`",    inline=False)
            embed.add_field(name="🎛️  Buttons",  value="⏮ 🔁 ⏸ 🔀 ⏭ · 📋 🔉 ⏹ 🔊",             inline=False)
            embed.add_field(name="💡  Tips",     value="• Works with song names, URLs, or YouTube Music links\n• Controls always move to latest message", inline=False)
            embed.set_footer(text="Example: $play never gonna give you up")
            return await ctx.send(embed=embed)

        if not ctx.author.voice:
            return await ctx.send(embed=discord.Embed(
                description="❌ Join a voice channel first!", color=discord.Color.red()), ephemeral=True)

        await ctx.typing()

        if ctx.interaction is None:
            try: await ctx.message.delete()
            except Exception: pass

        track = await fetch_track(query)
        if not track:
            return await ctx.send(embed=discord.Embed(
                description="❌ Couldn't find that song!", color=discord.Color.red()))

        track["requester"] = ctx.author.display_name
        await self._queue_or_play(ctx.guild, ctx.author.voice.channel, ctx.channel, track)

    @commands.command(name="skip", aliases=["s"])
    async def skip(self, ctx: commands.Context):
        p = get_player(ctx.guild.id)
        if not p or not p.current:
            return await ctx.send(embed=discord.Embed(
                description="❌ Nothing playing!", color=discord.Color.red()), delete_after=5)
        title = p.current["title"]
        p.skip()
        await ctx.send(embed=discord.Embed(description=f"⏭ Skipped **{title}**", color=PINK), delete_after=5)
        try: await ctx.message.delete()
        except Exception: pass

    @commands.command(name="pause", aliases=["resume"])
    async def pause(self, ctx: commands.Context):
        p = get_player(ctx.guild.id)
        if not p or not p.current:
            return await ctx.send(embed=discord.Embed(
                description="❌ Nothing playing!", color=discord.Color.red()), delete_after=5)
        paused = p.toggle_pause()
        label  = "⏸ Paused" if paused else "▶ Resumed"
        await ctx.send(embed=discord.Embed(
            description=f"{label} **{p.current['title']}**", color=PINK), delete_after=5)
        if p.np_msg:
            try:
                view = MusicControlView(self, ctx.guild.id)
                await p.np_msg.edit(embed=build_np_embed(p.current, len(p.queue), p.paused, p.loop, p.volume_pct), view=view)
            except Exception: pass
        try: await ctx.message.delete()
        except Exception: pass

    @commands.command(name="remove")
    async def remove(self, ctx: commands.Context, index: int = -1):
        p = get_player(ctx.guild.id)
        if not p or not p.queue:
            return await ctx.send(embed=discord.Embed(
                description="❌ Queue is empty!", color=discord.Color.red()), delete_after=5)
        q      = list(p.queue)
        target = len(q) - 1 if index == -1 else index - 1
        if target < 0 or target >= len(q):
            return await ctx.send(embed=discord.Embed(
                description=f"❌ Invalid position. Queue has {len(q)} song(s).", color=discord.Color.red()), delete_after=5)
        from collections import deque
        removed = q.pop(target)
        p.queue = deque(q)
        await ctx.send(embed=discord.Embed(
            description=f"🗑️ Removed **{removed['title']}**", color=PINK), delete_after=5)
        try: await ctx.message.delete()
        except Exception: pass

    @commands.command(name="search", aliases=["find"])
    async def search(self, ctx: commands.Context, *, query: str):
        if not ctx.author.voice:
            return await ctx.send(embed=discord.Embed(
                description="❌ Join a voice channel first!", color=discord.Color.red()), delete_after=5)
        try: await ctx.message.delete()
        except Exception: pass
        msg = await ctx.send(embed=discord.Embed(description=f"🔍 Searching **{query}**...", color=PINK))
        results = await search_tracks(query, 5)
        if not results:
            return await msg.edit(embed=discord.Embed(description="❌ No results found.", color=discord.Color.red()))
        lines = [f"`{i}.` **{r['title'][:60]}** · {format_duration(r.get('duration',0))}"
                 for i, r in enumerate(results, 1)]
        embed = discord.Embed(title=f"🔍  \"{query}\"", description="\n".join(lines), color=PINK)
        embed.set_footer(text="Pick a song below • 30s to choose")
        await msg.edit(embed=embed, view=SearchView(self, results, ctx.author.display_name))


async def setup(bot):
    await bot.add_cog(Music(bot))