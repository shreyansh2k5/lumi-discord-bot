# cogs/music.py
# Discord commands and UI only.
# All audio/queue/yt-dlp logic lives in music/engine.py.

import asyncio
import discord
from discord.ext import commands

from core.embeds import PINK
from music.embeds import build_np_embed
from music.engine import (
    GuildQueue,
    fetch_meta,
    create_source,
    search_tracks,
    fmt_time,
)


# ── Feature 1: Interactive Control Buttons ────────────────────────────────────

class MusicControlView(discord.ui.View):
    """
    Attached to every "Now Playing" embed.
    Buttons:
    - Row 0: Previous (⏮), Play/Pause (⏸/▶), Next (⏭)
    - Row 1: Leave VC (⏹), Repeat (🔁)

    After every interaction, the "Now Playing" embed moves to the bottom of the chat.
    No user messages are deleted.
    """

    def __init__(self, cog: "Music", ctx: commands.Context) -> None:
        super().__init__(timeout=3600)   # buttons live for 1 hour
        self.cog = cog
        self.ctx = ctx
        
        queue = cog.get_queue(ctx.guild.id)
        vc = ctx.voice_client
        paused = vc and vc.is_paused()
        loop_enabled = getattr(queue, "loop", False)

        # Row 0
        self.btn_previous = discord.ui.Button(emoji="⏮", style=discord.ButtonStyle.secondary, row=0)
        self.btn_previous.callback = self.do_previous
        self.add_item(self.btn_previous)

        self.btn_pause_resume = discord.ui.Button(
            emoji="▶" if paused else "⏸", 
            style=discord.ButtonStyle.secondary if paused else discord.ButtonStyle.primary,
            row=0
        )
        self.btn_pause_resume.callback = self.do_pause_resume
        self.add_item(self.btn_pause_resume)

        self.btn_skip = discord.ui.Button(emoji="⏭", style=discord.ButtonStyle.secondary, row=0)
        self.btn_skip.callback = self.do_skip
        self.add_item(self.btn_skip)

        # Row 1
        self.btn_leave = discord.ui.Button(emoji="⏹", style=discord.ButtonStyle.danger, row=1)
        self.btn_leave.callback = self.do_leave
        self.add_item(self.btn_leave)

        self.btn_repeat = discord.ui.Button(
            emoji="🔁", 
            style=discord.ButtonStyle.success if loop_enabled else discord.ButtonStyle.secondary, 
            row=1
        )
        self.btn_repeat.callback = self.do_repeat
        self.add_item(self.btn_repeat)

    async def _move_to_bottom(self, interaction: discord.Interaction):
        """Disables old message buttons, then sends a fresh embed at the bottom."""
        try:
            # Disable current buttons
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(view=self)
        except Exception:
            pass
            
        queue = self.cog.get_queue(self.ctx.guild.id)
        vc = self.ctx.voice_client
        if not vc or not queue.current:
            return
            
        vol_pct = int(vc.source.volume * 100) if getattr(vc, "source", None) else 100
        embed = build_np_embed(
            queue.current, 
            len(queue.queue), 
            vc.is_paused(), 
            queue.loop, 
            vol_pct
        )
        view = MusicControlView(self.cog, self.ctx)
        
        # Send new message
        queue.np_msg = await interaction.followup.send(embed=embed, view=view, wait=True)

    async def do_pause_resume(self, interaction: discord.Interaction) -> None:
        vc = self.ctx.voice_client
        if not vc:
            return await interaction.response.send_message("Not in a voice channel.", ephemeral=True)
        
        if vc.is_playing():
            vc.pause()
        elif vc.is_paused():
            vc.resume()
        else:
            return await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)
            
        await self._move_to_bottom(interaction)

    async def do_skip(self, interaction: discord.Interaction) -> None:
        vc = self.ctx.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            queue = self.cog.get_queue(self.ctx.guild.id)
            queue.skip_flag = True
            # We don't manually move to bottom here because vc.stop() triggers _play_next
            # which automatically sends the new track's embed.
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(view=self)
            vc.stop()
        else:
            await interaction.response.send_message("Nothing to skip.", ephemeral=True)

    async def do_previous(self, interaction: discord.Interaction) -> None:
        queue = self.cog.get_queue(self.ctx.guild.id)
        vc = self.ctx.voice_client
        
        if not queue.history:
            return await interaction.response.send_message("No previous track found in history.", ephemeral=True)
            
        if not vc:
            return await interaction.response.send_message("Not playing anything.", ephemeral=True)

        prev_track = queue.history.pop()
        
        # Put the current track back on top of the queue so it plays after
        if queue.current:
            queue.queue.insert(0, queue.current)
            
        # Put the previous track at the very top so it's picked up right now
        queue.queue.insert(0, prev_track)
        queue.skip_flag = True # prevents current song from looping back
        
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        vc.stop() # triggers _play_next

    async def do_leave(self, interaction: discord.Interaction) -> None:
        queue = self.cog.get_queue(self.ctx.guild.id)
        queue.clear()
        vc = self.ctx.voice_client
        if vc:
            await vc.disconnect()
            
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("⏹ Left the voice channel.", ephemeral=True)

    async def do_repeat(self, interaction: discord.Interaction) -> None:
        queue = self.cog.get_queue(self.ctx.guild.id)
        queue.loop = not queue.loop
        await self._move_to_bottom(interaction)


# ── Feature 2: Search Dropdown UI ────────────────────────────────────────────

class SearchSelect(discord.ui.Select):
    """
    Dropdown populated with up to 5 SoundCloud search results.
    """
    def __init__(
        self,
        cog:     "Music",
        ctx:     commands.Context,
        results: list[dict],
    ) -> None:
        self.cog     = cog
        self.ctx     = ctx
        self.results = results

        options = [
            discord.SelectOption(
                label=r["title"][:100],
                description=fmt_time(r.get("duration", 0)),
                value=str(i),
            )
            for i, r in enumerate(results)
        ]
        super().__init__(
            placeholder="🎵  Choose a song to play...",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        track = dict(self.results[int(self.values[0])])
        track["requester"] = interaction.user.display_name

        if not interaction.user.voice:
            return await interaction.followup.send("❌ Join a voice channel first.", ephemeral=True)

        vc = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            vc = await self.cog._connect(self.ctx)

        queue = self.cog.get_queue(self.ctx.guild.id)
        queue.queue.append(track)

        if vc.is_playing() or vc.is_paused():
            await interaction.followup.send(embed=discord.Embed(
                description=(
                    f"📋 Added to queue: **{track['title']}** "
                    f"`[{fmt_time(track.get('duration', 0))}]`\n"
                    f"Position: **#{len(queue.queue)}**"
                ),
                color=PINK,
            ))
        else:
            # Disable the search view
            try:
                for item in self.view.children:
                    item.disabled = True
                await interaction.edit_original_response(view=self.view)
            except Exception:
                pass
            
            # Start player
            await self.cog._play_next(self.ctx)


class SearchView(discord.ui.View):
    def __init__(self, cog: "Music", ctx: commands.Context, results: list[dict]) -> None:
        super().__init__(timeout=60)
        self.add_item(SearchSelect(cog, ctx, results))


# ── Music Cog ─────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot    = bot
        self.queues: dict[int, GuildQueue] = {}

    def get_queue(self, guild_id: int) -> GuildQueue:
        if guild_id not in self.queues:
            self.queues[guild_id] = GuildQueue()
        return self.queues[guild_id]

    def _schedule_next(self, ctx: commands.Context) -> None:
        asyncio.run_coroutine_threadsafe(self._play_next(ctx), self.bot.loop)

    def _after_track(self, error, ctx: commands.Context) -> None:
        if error:
            print(f"[Music] FFmpeg error: {error}")
        self._schedule_next(ctx)

    async def _play_next(self, ctx: commands.Context) -> None:
        queue = self.get_queue(ctx.guild.id)

        # Handle history and looping
        if queue.current:
            if not queue.loop:
                # Add to history if safely finished or skipped
                queue.history.append(queue.current)
                if len(queue.history) > 50:
                    queue.history.pop(0)
            
            # Re-queue the current track if looping and not explicitly skipped
            if queue.loop and not queue.skip_flag:
                queue.queue.insert(0, queue.current)
        
        queue.skip_flag = False

        if not queue.queue:
            queue.current = None
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
            return

        try:
            print(f"[Music] Fetching fresh stream → {track['title']}")
            player = await create_source(track, self.bot.loop)
        except Exception as exc:
            print(f"[Music] Stream fetch failed for '{track['title']}': {exc}")
            await ctx.send(embed=discord.Embed(
                description=(f"⚠️ Skipped **{track['title']}** — stream unavailable.\n`{exc}`"),
                color=discord.Color.orange(),
            ))
            await self._play_next(ctx)
            return

        try:
            ctx.voice_client.play(player, after=lambda e: self._after_track(e, ctx))
        except discord.ClientException as exc:
            print(f"[Music] vc.play() error: {exc}")
            return

        # Disable previous Now Playing embed if any
        if queue.np_msg:
            try:
                view = discord.ui.View.from_message(queue.np_msg)
                if view:
                    for item in view.children:
                        item.disabled = True
                    await queue.np_msg.edit(view=view)
            except Exception:
                pass

        # Send fresh NP embed at the bottom
        vol_pct = int(player.volume * 100)
        embed = build_np_embed(queue.current, len(queue.queue), False, queue.loop, vol_pct)
        view = MusicControlView(self, ctx)
        queue.np_msg = await ctx.send(embed=embed, view=view)

    async def _connect(self, ctx: commands.Context) -> discord.VoiceClient:
        channel = ctx.author.voice.channel
        needs_override = channel.rtc_region not in ("singapore", "us-west", "us-east", "us-central")
        if needs_override:
            try:
                await channel.edit(rtc_region="singapore")
                print(f"[Music] Overrode VC region → singapore (was {channel.rtc_region!r})")
            except discord.Forbidden:
                print("[Music] ⚠ Missing Manage Channels — cannot override VC region")
            except Exception as exc:
                print(f"[Music] Region edit error: {exc}")

        vc = ctx.voice_client
        if not vc:
            vc = await channel.connect()
        elif vc.channel != channel:
            await vc.move_to(channel)
        return vc

    @commands.hybrid_command(name="play", description="Play a song or search SoundCloud")
    async def play(self, ctx: commands.Context, *, query: str) -> None:
        if not ctx.author.voice:
            return await ctx.send("❌ Join a voice channel first.")

        vc = await self._connect(ctx)
        await ctx.typing()

        search = f"scsearch1:{query}" if not query.startswith("http") else query

        try:
            track = await fetch_meta(search, self.bot.loop)
            track["requester"] = ctx.author.display_name
        except Exception as exc:
            return await ctx.send(f"❌ Could not find that song: {exc}")

        queue = self.get_queue(ctx.guild.id)
        queue.queue.append(track)

        if vc.is_playing() or vc.is_paused():
            await ctx.send(embed=discord.Embed(
                description=(f"📋 Added to queue: **{track['title']}** `[{fmt_time(track['duration'])}]`\nPosition: **#{len(queue.queue)}**"),
                color=PINK,
            ))
        else:
            await self._play_next(ctx)

    @commands.hybrid_command(name="search", description="Search SoundCloud and pick a song")
    async def search(self, ctx: commands.Context, *, query: str) -> None:
        if not ctx.author.voice:
            return await ctx.send("❌ Join a voice channel first.")

        await ctx.typing()
        results = await search_tracks(query, self.bot.loop, limit=5)
        if not results:
            return await ctx.send("❌ No results found for that query.")

        await self._connect(ctx)

        lines = [f"`{i+1}.` **{r['title']}** `[{fmt_time(r.get('duration', 0))}]`" for i, r in enumerate(results)]
        embed = discord.Embed(
            title=f"🔍  Results for: {query}",
            description="\n".join(lines),
            color=PINK,
        )
        embed.set_footer(text="Pick a song from the dropdown · expires in 60 s")
        await ctx.send(embed=embed, view=SearchView(self, ctx, results))

    @commands.hybrid_command(name="skip", description="Skip the current song")
    async def skip(self, ctx: commands.Context) -> None:
        queue = self.get_queue(ctx.guild.id)
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            queue.skip_flag = True
            ctx.voice_client.stop()
            await ctx.send("⏭ Skipped.")
        else:
            await ctx.send("❌ Nothing is playing.")

    @commands.hybrid_command(name="pause", description="Pause playback")
    async def pause(self, ctx: commands.Context) -> None:
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            
            queue = self.get_queue(ctx.guild.id)
            if queue.np_msg:
                try:
                    view = discord.ui.View.from_message(queue.np_msg)
                    if view:
                        for item in view.children: item.disabled = True
                        await queue.np_msg.edit(view=view)
                except: pass
            
            vol_pct = int(ctx.voice_client.source.volume * 100) if getattr(ctx.voice_client, "source", None) else 100
            embed = build_np_embed(queue.current, len(queue.queue), True, queue.loop, vol_pct)
            view = MusicControlView(self, ctx)
            queue.np_msg = await ctx.send(embed=embed, view=view)
        else:
            await ctx.send("❌ Nothing is playing.")

    @commands.hybrid_command(name="resume", description="Resume playback")
    async def resume(self, ctx: commands.Context) -> None:
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            
            queue = self.get_queue(ctx.guild.id)
            if queue.np_msg:
                try:
                    view = discord.ui.View.from_message(queue.np_msg)
                    if view:
                        for item in view.children: item.disabled = True
                        await queue.np_msg.edit(view=view)
                except: pass
            
            vol_pct = int(ctx.voice_client.source.volume * 100) if getattr(ctx.voice_client, "source", None) else 100
            embed = build_np_embed(queue.current, len(queue.queue), False, queue.loop, vol_pct)
            view = MusicControlView(self, ctx)
            queue.np_msg = await ctx.send(embed=embed, view=view)
        else:
            await ctx.send("❌ Nothing is paused.")

    @commands.hybrid_command(name="queue", description="Show the current queue")
    async def queue_cmd(self, ctx: commands.Context) -> None:
        queue = self.get_queue(ctx.guild.id)
        if not queue.queue and not queue.current:
            return await ctx.send("📋 Queue is empty.")

        lines: list[str] = []
        if queue.current:
            lines.append(f"▶ **Now:** {queue.current['title']} `[{fmt_time(queue.current.get('duration', 0))}]`")
        for i, song in enumerate(queue.queue[:10], 1):
            lines.append(f"`{i}.` {song['title']} `[{fmt_time(song.get('duration', 0))}]`")
        if len(queue.queue) > 10:
            lines.append(f"*…and {len(queue.queue) - 10} more*")

        await ctx.send(embed=discord.Embed(title="📋  Queue", description="\n".join(lines), color=PINK))

    @commands.hybrid_command(name="nowplaying", aliases=["np"], description="Show current song")
    async def nowplaying(self, ctx: commands.Context) -> None:
        queue = self.get_queue(ctx.guild.id)
        vc = ctx.voice_client
        if not queue.current or not vc:
            return await ctx.send("❌ Nothing is playing.")
            
        if queue.np_msg:
            try:
                view = discord.ui.View.from_message(queue.np_msg)
                if view:
                    for item in view.children: item.disabled = True
                    await queue.np_msg.edit(view=view)
            except: pass
            
        vol_pct = int(vc.source.volume * 100) if getattr(vc, "source", None) else 100
        embed = build_np_embed(queue.current, len(queue.queue), vc.is_paused(), queue.loop, vol_pct)
        view = MusicControlView(self, ctx)
        queue.np_msg = await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="stop", description="Stop playback and disconnect")
    async def stop(self, ctx: commands.Context) -> None:
        queue = self.get_queue(ctx.guild.id)
        queue.clear()
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        await ctx.send("⏹ Stopped and disconnected.")

    @commands.hybrid_command(name="volume", description="Set volume (10–200)")
    async def volume(self, ctx: commands.Context, vol: int) -> None:
        queue = self.get_queue(ctx.guild.id)
        vc = ctx.voice_client
        if not vc or not vc.source:
            return await ctx.send("❌ Nothing is playing.")
        
        vol = max(10, min(200, vol))
        vc.source.volume = vol / 100
        await ctx.send(f"🔊 Volume set to **{vol}%**")
        
        # update embed
        if queue.np_msg and queue.current:
            try:
                view = discord.ui.View.from_message(queue.np_msg)
                if view:
                    for item in view.children: item.disabled = True
                    await queue.np_msg.edit(view=view)
            except: pass
            embed = build_np_embed(queue.current, len(queue.queue), vc.is_paused(), queue.loop, vol)
            view = MusicControlView(self, ctx)
            queue.np_msg = await ctx.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        if member.id != self.bot.user.id:
            return
        if before.channel and after.channel is None:
            try:
                await before.channel.edit(rtc_region=None)
                print(f"[Music] Restored VC region → auto for #{before.channel.name}")
            except Exception:
                pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))