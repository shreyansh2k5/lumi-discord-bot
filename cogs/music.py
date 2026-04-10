# cogs/music.py
# Discord commands only — all audio/queue logic lives in music/engine.py

import asyncio
import discord
from discord.ext import commands

from core.embeds import PINK
from music.engine import (
    GuildQueue,
    fetch_meta,
    create_source,
    fmt_time,
)


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

    def _schedule_next(self, ctx: commands.Context) -> None:
        """
        Bridge from the non-async FFmpeg after= callback thread to the
        asyncio event loop. run_coroutine_threadsafe is the only correct API.
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
                description=f"⚠️ Skipped **{track['title']}** — stream unavailable.\n`{exc}`",
                color=discord.Color.orange(),
            ))
            await self._play_next(ctx)   # try the next track instead
            return

        try:
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
        ))

    # ── Voice connection ──────────────────────────────────────────────────────

    async def _connect(self, ctx: commands.Context) -> discord.VoiceClient:
        """
        Join the user's voice channel and pin the region to Singapore.

        Azure India datacenters drop outbound UDP to Discord's Mumbai voice
        servers, causing a 4006 disconnect after ~30 s of "silence".
        Overriding rtc_region to 'singapore' avoids this entirely.
        The region is restored to auto (None) when the bot disconnects.
        """
        channel = ctx.author.voice.channel

        needs_override = channel.rtc_region not in ("singapore", "us-west",
                                                     "us-east", "us-central")
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

    # ── Commands ──────────────────────────────────────────────────────────────

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

            vc.play(player, after=lambda e: self._after_track(e, ctx))
            await ctx.send(embed=discord.Embed(
                description=(
                    f"🎶 Now playing: **{player.title}** "
                    f"`[{fmt_time(player.duration)}]`\n"
                    f"👤 Requested by **{player.requester}**"
                ),
                color=PINK,
            ))

    @commands.hybrid_command(name="skip", description="Skip the current song")
    async def skip(self, ctx: commands.Context) -> None:
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
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
            title="📋 Queue",
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
            title="🎵 Now Playing",
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
                print(f"[Music] Restored VC region → auto for #{before.channel.name}")
            except Exception:
                pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))