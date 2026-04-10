# cogs/music.py
# Discord commands and UI only.
# All audio/queue/yt-dlp logic lives in music/engine.py.

import asyncio
import discord
from discord.ext import commands

from core.embeds import PINK
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
    Three buttons — ⏸ Pause/Resume, ⏭ Skip, ⏹ Stop — that replicate the
    exact same logic as the $pause/$resume, $skip, and $stop text commands.

    No messages are ever deleted by these buttons.
    """

    def __init__(self, cog: "Music", ctx: commands.Context) -> None:
        super().__init__(timeout=3600)   # buttons live for 1 hour
        self.cog = cog
        self.ctx = ctx

    # ── ⏸ / ▶ toggle ────────────────────────────────────────────────────────

    @discord.ui.button(emoji="⏸", style=discord.ButtonStyle.primary)
    async def btn_pause_resume(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        vc = self.ctx.voice_client
        if not vc:
            return await interaction.response.send_message(
                "Not in a voice channel.", ephemeral=True
            )
        if vc.is_playing():
            vc.pause()
            button.emoji = discord.PartialEmoji(name="▶")
            button.style = discord.ButtonStyle.secondary
        elif vc.is_paused():
            vc.resume()
            button.emoji = discord.PartialEmoji(name="⏸")
            button.style = discord.ButtonStyle.primary
        else:
            return await interaction.response.send_message(
                "Nothing is playing right now.", ephemeral=True
            )
        await interaction.response.edit_message(view=self)

    # ── ⏭ Skip ──────────────────────────────────────────────────────────────

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.secondary)
    async def btn_skip(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        vc = self.ctx.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()   # triggers after= → _schedule_next → _play_next
            await interaction.response.send_message("⏭ Skipped.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "Nothing to skip.", ephemeral=True
            )

    # ── ⏹ Stop ──────────────────────────────────────────────────────────────

    @discord.ui.button(emoji="⏹", style=discord.ButtonStyle.danger)
    async def btn_stop(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        queue = self.cog.get_queue(self.ctx.guild.id)
        queue.clear()
        vc = self.ctx.voice_client
        if vc:
            await vc.disconnect()
        # Disable all buttons so old embeds can't be clicked after stopping
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)


# ── Feature 2: Search Dropdown UI ────────────────────────────────────────────

class SearchSelect(discord.ui.Select):
    """
    Dropdown populated with up to 5 SoundCloud search results.
    On selection, replicates the exact queue-or-play logic of $play.
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

        track            = dict(self.results[int(self.values[0])])
        track["requester"] = interaction.user.display_name

        # Ensure the selecting user is still in a voice channel
        if not interaction.user.voice:
            return await interaction.followup.send(
                "❌ Join a voice channel first.", ephemeral=True
            )

        # Use the guild's current voice client (may already be connected)
        vc = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            vc = await self.cog._connect(self.ctx)

        queue = self.cog.get_queue(self.ctx.guild.id)

        if vc.is_playing() or vc.is_paused():
            queue.queue.append(track)
            await interaction.followup.send(embed=discord.Embed(
                description=(
                    f"📋 Added to queue: **{track['title']}** "
                    f"`[{fmt_time(track.get('duration', 0))}]`\n"
                    f"Position: **#{len(queue.queue)}**"
                ),
                color=PINK,
            ))
        else:
            queue.current = track
            try:
                player = await create_source(track, self.cog.bot.loop)
            except Exception as exc:
                queue.current = None
                return await interaction.followup.send(
                    f"❌ Failed to load stream: {exc}", ephemeral=True
                )
            view = MusicControlView(self.cog, self.ctx)
            vc.play(player, after=lambda e: self.cog._after_track(e, self.ctx))
            await interaction.followup.send(embed=discord.Embed(
                description=(
                    f"🎶 Now playing: **{player.title}** "
                    f"`[{fmt_time(player.duration)}]`\n"
                    f"👤 Requested by **{player.requester}**"
                ),
                color=PINK,
            ), view=view)


class SearchView(discord.ui.View):
    """Wraps SearchSelect with a 60-second timeout."""

    def __init__(
        self,
        cog:     "Music",
        ctx:     commands.Context,
        results: list[dict],
    ) -> None:
        super().__init__(timeout=60)
        self.add_item(SearchSelect(cog, ctx, results))


# ── Music Cog ─────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot    = bot
        self.queues: dict[int, GuildQueue] = {}

    # ── Queue registry ────────────────────────────────────────────────────────

    def get_queue(self, guild_id: int) -> GuildQueue:
        if guild_id not in self.queues:
            self.queues[guild_id] = GuildQueue()
        return self.queues[guild_id]

    # ── Playback engine ───────────────────────────────────────────────────────
    # NOTE: _schedule_next, _after_track, and _play_next are intentionally
    # untouched. Do not modify these without also verifying the Azure/Singapore
    # region fix and the lazy stream-fetch logic remain intact.

    def _schedule_next(self, ctx: commands.Context) -> None:
        """
        Bridge from the non-async FFmpeg after= callback thread to the asyncio
        event loop. run_coroutine_threadsafe is the only correct API here.
        """
        asyncio.run_coroutine_threadsafe(self._play_next(ctx), self.bot.loop)

    def _after_track(self, error, ctx: commands.Context) -> None:
        if error:
            print(f"[Music] FFmpeg error: {error}")
        self._schedule_next(ctx)

    async def _play_next(self, ctx: commands.Context) -> None:
        """
        Pop the next track dict, fetch a FRESH stream URL right now, and play.
        On failure, skip to the next track and notify the channel.
        """
        queue = self.get_queue(ctx.guild.id)

        if not queue.queue:
            queue.current = None
            await asyncio.sleep(300)          # 5-min idle grace period
            if ctx.voice_client and not ctx.voice_client.is_playing():
                try:
                    await ctx.voice_client.disconnect()
                except Exception:
                    pass
            return

        track         = queue.queue.pop(0)
        queue.current = track

        if not ctx.voice_client or not ctx.voice_client.is_connected():
            return

        try:
            print(f"[Music] Fetching fresh stream → {track['title']}")
            player = await create_source(track, self.bot.loop)
        except Exception as exc:
            print(f"[Music] Stream fetch failed for '{track['title']}': {exc}")
            await ctx.send(embed=discord.Embed(
                description=(
                    f"⚠️ Skipped **{track['title']}** — stream unavailable.\n`{exc}`"
                ),
                color=discord.Color.orange(),
            ))
            await self._play_next(ctx)
            return

        try:
            view = MusicControlView(self, ctx)
            ctx.voice_client.play(player, after=lambda e: self._after_track(e, ctx))
        except discord.ClientException as exc:
            print(f"[Music] vc.play() error: {exc}")
            return

        await ctx.send(embed=discord.Embed(
            description=(
                f"🎶 Now playing: **{player.title}** `[{fmt_time(player.duration)}]`\n"
                f"👤 Requested by **{player.requester}**"
            ),
            color=PINK,
        ), view=view)

    # ── Voice connection ──────────────────────────────────────────────────────
    # NOTE: Do not alter _connect — it contains the Azure UDP/4006 region fix.

    async def _connect(self, ctx: commands.Context) -> discord.VoiceClient:
        """
        Join the user's voice channel and pin the region to Singapore.

        Azure India datacenters drop outbound UDP to Discord's Mumbai voice
        servers, causing a 4006 disconnect after ~30 s of perceived silence.
        Overriding rtc_region to 'singapore' avoids this entirely. The region
        is restored to auto (None) when the bot disconnects.
        """
        channel = ctx.author.voice.channel

        needs_override = channel.rtc_region not in (
            "singapore", "us-west", "us-east", "us-central"
        )
        if needs_override:
            try:
                await channel.edit(rtc_region="singapore")
                print(
                    f"[Music] Overrode VC region → singapore "
                    f"(was {channel.rtc_region!r})"
                )
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

    # ── Commands ──────────────────────────────────────────────────────────────
    # Feature 3: No ctx.message.delete() calls anywhere — user messages are
    # always preserved in channel history.

    @commands.hybrid_command(name="play", description="Play a song or search SoundCloud")
    async def play(self, ctx: commands.Context, *, query: str) -> None:
        if not ctx.author.voice:
            return await ctx.send("❌ Join a voice channel first.")

        vc = await self._connect(ctx)
        await ctx.typing()

        search = f"scsearch1:{query}" if not query.startswith("http") else query

        try:
            track            = await fetch_meta(search, self.bot.loop)
            track["requester"] = ctx.author.display_name
        except Exception as exc:
            return await ctx.send(f"❌ Could not find that song: {exc}")

        queue = self.get_queue(ctx.guild.id)

        if vc.is_playing() or vc.is_paused():
            queue.queue.append(track)
            await ctx.send(embed=discord.Embed(
                description=(
                    f"📋 Added to queue: **{track['title']}** "
                    f"`[{fmt_time(track['duration'])}]`\n"
                    f"Position: **#{len(queue.queue)}**"
                ),
                color=PINK,
            ))
        else:
            queue.current = track
            try:
                player = await create_source(track, self.bot.loop)
            except Exception as exc:
                queue.current = None
                return await ctx.send(f"❌ Failed to load stream: {exc}")

            view = MusicControlView(self, ctx)
            vc.play(player, after=lambda e: self._after_track(e, ctx))
            await ctx.send(embed=discord.Embed(
                description=(
                    f"🎶 Now playing: **{player.title}** "
                    f"`[{fmt_time(player.duration)}]`\n"
                    f"👤 Requested by **{player.requester}**"
                ),
                color=PINK,
            ), view=view)

    @commands.hybrid_command(name="search", description="Search SoundCloud and pick a song")
    async def search(self, ctx: commands.Context, *, query: str) -> None:
        if not ctx.author.voice:
            return await ctx.send("❌ Join a voice channel first.")

        await ctx.typing()

        results = await search_tracks(query, self.bot.loop, limit=5)
        if not results:
            return await ctx.send("❌ No results found for that query.")

        # Pre-connect so SearchSelect can immediately play if nothing is queued
        await self._connect(ctx)

        lines = [
            f"`{i+1}.` **{r['title']}** `[{fmt_time(r.get('duration', 0))}]`"
            for i, r in enumerate(results)
        ]
        embed = discord.Embed(
            title=f"🔍  Results for: {query}",
            description="\n".join(lines),
            color=PINK,
        )
        embed.set_footer(text="Pick a song from the dropdown · expires in 60 s")
        await ctx.send(embed=embed, view=SearchView(self, ctx, results))

    @commands.hybrid_command(name="skip", description="Skip the current song")
    async def skip(self, ctx: commands.Context) -> None:
        if ctx.voice_client and (
            ctx.voice_client.is_playing() or ctx.voice_client.is_paused()
        ):
            ctx.voice_client.stop()
            await ctx.send("⏭ Skipped.")
        else:
            await ctx.send("❌ Nothing is playing.")

    @commands.hybrid_command(name="pause", description="Pause playback")
    async def pause(self, ctx: commands.Context) -> None:
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸ Paused.")
        else:
            await ctx.send("❌ Nothing is playing.")

    @commands.hybrid_command(name="resume", description="Resume playback")
    async def resume(self, ctx: commands.Context) -> None:
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶ Resumed.")
        else:
            await ctx.send("❌ Nothing is paused.")

    @commands.hybrid_command(name="queue", description="Show the current queue")
    async def queue_cmd(self, ctx: commands.Context) -> None:
        queue = self.get_queue(ctx.guild.id)
        if not queue.queue and not queue.current:
            return await ctx.send("📋 Queue is empty.")

        lines: list[str] = []
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
            title="📋  Queue",
            description="\n".join(lines),
            color=PINK,
        ))

    @commands.hybrid_command(name="nowplaying", aliases=["np"], description="Show current song")
    async def nowplaying(self, ctx: commands.Context) -> None:
        queue = self.get_queue(ctx.guild.id)
        if not queue.current:
            return await ctx.send("❌ Nothing is playing.")
        t = queue.current
        await ctx.send(embed=discord.Embed(
            title="🎵  Now Playing",
            description=(
                f"**{t['title']}** `[{fmt_time(t.get('duration', 0))}]`\n"
                f"👤 Requested by **{t.get('requester', 'Unknown')}**"
            ),
            color=PINK,
        ))

    @commands.hybrid_command(name="stop", description="Stop playback and disconnect")
    async def stop(self, ctx: commands.Context) -> None:
        queue = self.get_queue(ctx.guild.id)
        queue.clear()
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        await ctx.send("⏹ Stopped and disconnected.")

    @commands.hybrid_command(name="volume", description="Set volume (10–200)")
    async def volume(self, ctx: commands.Context, vol: int) -> None:
        if not ctx.voice_client or not ctx.voice_client.source:
            return await ctx.send("❌ Nothing is playing.")
        vol = max(10, min(200, vol))
        ctx.voice_client.source.volume = vol / 100
        await ctx.send(f"🔊 Volume set to **{vol}%**")

    # ── Region restore on disconnect ──────────────────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before:  discord.VoiceState,
        after:   discord.VoiceState,
    ) -> None:
        if member.id != self.bot.user.id:
            return
        if before.channel and after.channel is None:
            try:
                await before.channel.edit(rtc_region=None)
                print(
                    f"[Music] Restored VC region → auto "
                    f"for #{before.channel.name}"
                )
            except Exception:
                pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))