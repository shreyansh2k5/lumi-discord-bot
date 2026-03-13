# cogs/music.py

import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from music.ytdl import fetch_track, search_tracks, format_duration
from music.player import get_player, create_player, remove_player, GuildPlayer
from core.embeds import PINK


# ── Now-Playing embed ─────────────────────────────────────────────

def build_now_playing_embed(player: GuildPlayer) -> discord.Embed:
    track = player.current
    if not track:
        return discord.Embed(description="Nothing playing.", color=PINK)

    embed = discord.Embed(
        title="🎵  Now Playing",
        description=f"**[{track['title']}]({track['webpage_url']})**",
        color=PINK
    )
    embed.add_field(name="⏱ Duration",  value=format_duration(track["duration"]), inline=True)
    embed.add_field(name="👤 Requester", value=track.get("requester", "Unknown"),  inline=True)
    embed.add_field(name="🔊 Volume",    value=f"{player.volume_percent}%",         inline=True)

    status_parts = []
    if player.loop:    status_parts.append("🔁 Loop")
    if player.shuffle: status_parts.append("🔀 Shuffle")
    if player.is_paused: status_parts.append("⏸ Paused")
    status_parts.append(f"📋 Queue: {len(player.queue)}")
    embed.add_field(name="Status", value=" · ".join(status_parts), inline=False)

    if track.get("thumbnail"):
        embed.set_thumbnail(url=track["thumbnail"])

    embed.set_footer(text="Lumi Music 🎶  •  Use the buttons to control playback")
    return embed


# ── Control buttons ───────────────────────────────────────────────

class MusicControlView(discord.ui.View):
    def __init__(self, cog: "Music", guild_id: int):
        super().__init__(timeout=None)
        self.cog      = cog
        self.guild_id = guild_id

    def _get_player(self) -> GuildPlayer | None:
        return get_player(self.guild_id)

    async def _refresh(self, interaction: discord.Interaction):
        player = self._get_player()
        if player and player.current:
            embed = build_now_playing_embed(player)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.edit_message(
                embed=discord.Embed(description="⏹ Playback stopped.", color=PINK),
                view=None
            )

    # Row 1
    @discord.ui.button(emoji="⏮", style=discord.ButtonStyle.secondary, row=0)
    async def btn_previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self._get_player()
        if not player or not player.current:
            return await interaction.response.send_message("Nothing is playing!", ephemeral=True)
        player.queue.appendleft(player.current)
        player.queue.appendleft(player.current)
        player.skip()
        await interaction.response.defer()

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=0)
    async def btn_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self._get_player()
        if not player:
            return await interaction.response.send_message("Nothing is playing!", ephemeral=True)
        player.loop = not player.loop
        button.style = discord.ButtonStyle.success if player.loop else discord.ButtonStyle.secondary
        await self._refresh(interaction)

    @discord.ui.button(emoji="⏸", style=discord.ButtonStyle.primary, row=0)
    async def btn_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self._get_player()
        if not player:
            return await interaction.response.send_message("Nothing is playing!", ephemeral=True)
        paused = player.toggle_pause()
        button.emoji = discord.PartialEmoji(name="▶" if paused else "⏸")
        button.style = discord.ButtonStyle.secondary if paused else discord.ButtonStyle.primary
        await self._refresh(interaction)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, row=0)
    async def btn_shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self._get_player()
        if not player:
            return await interaction.response.send_message("Nothing is playing!", ephemeral=True)
        player.shuffle = not player.shuffle
        button.style = discord.ButtonStyle.success if player.shuffle else discord.ButtonStyle.secondary
        await self._refresh(interaction)

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.secondary, row=0)
    async def btn_skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self._get_player()
        if not player or not player.current:
            return await interaction.response.send_message("Nothing to skip!", ephemeral=True)
        player.skip()
        await interaction.response.defer()

    # Row 2
    @discord.ui.button(emoji="🔉", style=discord.ButtonStyle.secondary, row=1)
    async def btn_vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self._get_player()
        if not player:
            return await interaction.response.send_message("Nothing is playing!", ephemeral=True)
        player.set_volume(-0.1)
        await self._refresh(interaction)

    @discord.ui.button(emoji="📋", style=discord.ButtonStyle.secondary, row=1)
    async def btn_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self._get_player()
        if not player or not player.queue_list:
            return await interaction.response.send_message("The queue is empty!", ephemeral=True)
        lines = [
            f"`{i}.` {t['title']} ({format_duration(t['duration'])})"
            for i, t in enumerate(player.queue_list[:10], start=1)
        ]
        if len(player.queue_list) > 10:
            lines.append(f"*...and {len(player.queue_list) - 10} more*")
        embed = discord.Embed(title="📋  Queue", description="\n".join(lines), color=PINK)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(emoji="⏹", style=discord.ButtonStyle.danger, row=1)
    async def btn_stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self._get_player()
        if not player:
            return await interaction.response.send_message("Nothing is playing!", ephemeral=True)
        player.stop()
        vc = player.voice_client
        remove_player(self.guild_id)
        await vc.disconnect()
        await interaction.response.edit_message(
            embed=discord.Embed(description="⏹ Stopped and disconnected.", color=PINK),
            view=None
        )

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, row=1)
    async def btn_vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self._get_player()
        if not player:
            return await interaction.response.send_message("Nothing is playing!", ephemeral=True)
        player.set_volume(0.1)
        await self._refresh(interaction)


# ── Search dropdown ───────────────────────────────────────────────

class SearchSelect(discord.ui.Select):
    def __init__(self, cog: "Music", results: list[dict], requester: str):
        self.cog       = cog
        self.results   = results
        self.requester = requester
        options = [
            discord.SelectOption(
                label=r["title"][:100],
                description=f"{format_duration(r['duration'])} · {r['uploader'][:40]}"[:100],
                value=str(i)
            )
            for i, r in enumerate(results)
        ]
        super().__init__(placeholder="🎵 Pick a song to play...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        chosen = self.results[int(self.values[0])]

        # Fetch full stream URL now (we only had flat info from search)
        track = await fetch_track(chosen["webpage_url"])
        if not track:
            return await interaction.followup.send("❌ Failed to load that track.", ephemeral=True)

        track["requester"] = self.requester

        # Disable the dropdown
        self.disabled = True
        await interaction.message.edit(
            embed=discord.Embed(
                description=f"✅ **{track['title']}** added!",
                color=PINK
            ),
            view=None
        )

        # Play via cog
        guild_id = interaction.guild_id
        player   = get_player(guild_id)

        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.followup.send("❌ Join a voice channel first!", ephemeral=True)

        vc_channel = interaction.user.voice.channel
        if player:
            if player.voice_client.channel != vc_channel:
                await player.voice_client.move_to(vc_channel)
        else:
            vc     = await vc_channel.connect()
            player = create_player(guild_id, vc)

        channel = interaction.channel
        if player.voice_client.is_playing() or player.voice_client.is_paused():
            player.queue.append(track)
            pos = len(player.queue)
            embed = discord.Embed(
                title="📋  Added to Queue",
                description=f"**{track['title']}**\n⏱ {format_duration(track['duration'])} · Position #{pos}",
                color=PINK
            )
            if track.get("thumbnail"):
                embed.set_thumbnail(url=track["thumbnail"])
            await interaction.followup.send(embed=embed)
            # Move now-playing to bottom
            await self.cog._move_now_playing(player, channel)
        else:
            player.queue.append(track)
            player.play_next(after=lambda e: self.cog._after_track(guild_id, channel))
            await self.cog._send_now_playing(player, channel)


class SearchView(discord.ui.View):
    def __init__(self, cog: "Music", results: list[dict], requester: str):
        super().__init__(timeout=30)
        self.add_item(SearchSelect(cog, results, requester))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


# ── Music Cog ─────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Internal helpers ─────────────────────────────────────────

    def _after_track(self, guild_id: int, channel: discord.TextChannel):
        asyncio.run_coroutine_threadsafe(
            self._advance(guild_id, channel),
            self.bot.loop
        )

    async def _advance(self, guild_id: int, channel: discord.TextChannel):
        player = get_player(guild_id)
        if not player:
            return
        if not player.queue and not player.loop:
            player.current = None
            if player.now_playing_message:
                try:
                    await player.now_playing_message.edit(
                        embed=discord.Embed(description="✅ Queue finished!", color=PINK),
                        view=None
                    )
                except Exception:
                    pass
            return
        player.play_next(after=lambda e: self._after_track(guild_id, channel))
        await self._move_now_playing(player, channel)

    async def _send_now_playing(self, player: GuildPlayer, channel: discord.TextChannel):
        """Sends a brand new now-playing message and stores the reference."""
        # Delete old one first so controls always appear at the bottom
        if player.now_playing_message:
            try:
                await player.now_playing_message.delete()
            except Exception:
                pass
        embed = build_now_playing_embed(player)
        view  = MusicControlView(self, channel.guild.id)
        player.now_playing_message = await channel.send(embed=embed, view=view)

    async def _move_now_playing(self, player: GuildPlayer, channel: discord.TextChannel):
        """
        When a new song is queued while something is playing,
        deletes the old controls and resends them at the bottom so they're always visible.
        """
        await self._send_now_playing(player, channel)

    # ── $play / /play ─────────────────────────────────────────────

    @commands.hybrid_command(name="play", description="Play a song from YouTube 🎵")
    @app_commands.describe(query="Song name or YouTube URL")
    async def play(self, ctx: commands.Context, *, query: str = None):

        # No query = show music help
        if not query:
            embed = discord.Embed(
                title="🎵  Lumi Music — Commands",
                description="Play music from YouTube directly in your voice channel!",
                color=PINK
            )
            embed.add_field(
                name="▶️  Play",
                value="""`$play <song name or URL>` — Play a song or add to queue
`$search <query>` — Pick from 5 search results""",
                inline=False
            )
            embed.add_field(
                name="⏯️  Controls",
                value="""`$skip` / `$s` — Skip current song
`$pause` / `$resume` — Toggle pause
`$remove` — Remove last queued song
`$remove <#>` — Remove song at position""",
                inline=False
            )
            embed.add_field(
                name="🎛️  Button Controls",
                value="""⏮ Previous  🔁 Loop  ⏸ Pause  🔀 Shuffle  ⏭ Skip
🔉 Volume−  📋 Queue  ⏹ Stop  🔊 Volume+""",
                inline=False
            )
            embed.add_field(
                name="💡  Tips",
                value="""• Works with song names, YouTube URLs, or search terms
• Queue songs while one is already playing
• Controls always move to the latest message""",
                inline=False
            )
            embed.set_footer(text="Example: $play never gonna give you up")
            return await ctx.send(embed=embed)

        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send(
                embed=discord.Embed(description="❌ Join a voice channel first!", color=discord.Color.red()),
                ephemeral=True
            )

        await ctx.typing()
        track = await fetch_track(query)
        if not track:
            return await ctx.send(
                embed=discord.Embed(description="❌ Couldn't find that song!", color=discord.Color.red())
            )

        track["requester"] = ctx.author.display_name
        guild_id   = ctx.guild.id
        player     = get_player(guild_id)
        vc_channel = ctx.author.voice.channel

        if player:
            if player.voice_client.channel != vc_channel:
                await player.voice_client.move_to(vc_channel)
        else:
            vc     = await vc_channel.connect()
            player = create_player(guild_id, vc)

        if ctx.interaction is None:
            try: await ctx.message.delete()
            except Exception: pass

        if player.voice_client.is_playing() or player.voice_client.is_paused():
            player.queue.append(track)
            pos   = len(player.queue)
            embed = discord.Embed(
                title="📋  Added to Queue",
                description=f"**{track['title']}**\n⏱ {format_duration(track['duration'])} · Position #{pos}",
                color=PINK
            )
            if track.get("thumbnail"):
                embed.set_thumbnail(url=track["thumbnail"])
            embed.set_footer(text="Lumi Music 🎶")
            msg = await ctx.send(embed=embed)
            # Move controls to bottom so they're always reachable
            await self._move_now_playing(player, ctx.channel)
            try: await msg.delete(delay=5)
            except Exception: pass
        else:
            player.queue.append(track)
            player.play_next(after=lambda e: self._after_track(guild_id, ctx.channel))
            await self._send_now_playing(player, ctx.channel)

    # ── $skip ─────────────────────────────────────────────────────

    @commands.command(name="skip", aliases=["s"])
    async def skip(self, ctx: commands.Context):
        player = get_player(ctx.guild.id)
        if not player or not player.current:
            return await ctx.send(
                embed=discord.Embed(description="❌ Nothing is playing!", color=discord.Color.red()),
                delete_after=5
            )
        title = player.current["title"]
        player.skip()
        msg = await ctx.send(
            embed=discord.Embed(description=f"⏭ Skipped **{title}**", color=PINK),
            delete_after=5
        )
        try: await ctx.message.delete()
        except Exception: pass

    # ── $pause ────────────────────────────────────────────────────

    @commands.command(name="pause", aliases=["resume"])
    async def pause(self, ctx: commands.Context):
        player = get_player(ctx.guild.id)
        if not player or not player.current:
            return await ctx.send(
                embed=discord.Embed(description="❌ Nothing is playing!", color=discord.Color.red()),
                delete_after=5
            )
        paused = player.toggle_pause()
        label  = "⏸ Paused" if paused else "▶ Resumed"
        await ctx.send(
            embed=discord.Embed(description=f"{label} **{player.current['title']}**", color=PINK),
            delete_after=5
        )
        # Update the controls embed to reflect pause state
        if player.now_playing_message:
            try:
                view = MusicControlView(self, ctx.guild.id)
                # Fix pause button appearance
                for item in view.children:
                    if hasattr(item, 'emoji') and item.emoji and str(item.emoji) in ("⏸", "▶"):
                        item.emoji = discord.PartialEmoji(name="▶" if paused else "⏸")
                        item.style = discord.ButtonStyle.secondary if paused else discord.ButtonStyle.primary
                await player.now_playing_message.edit(embed=build_now_playing_embed(player), view=view)
            except Exception:
                pass
        try: await ctx.message.delete()
        except Exception: pass

    # ── $remove ───────────────────────────────────────────────────

    @commands.command(name="remove")
    async def remove(self, ctx: commands.Context, index: int = -1):
        """
        Removes a song from the queue.
        $remove       → removes the last song added
        $remove 2     → removes song at position 2
        """
        player = get_player(ctx.guild.id)
        if not player or not player.queue_list:
            return await ctx.send(
                embed=discord.Embed(description="❌ The queue is empty!", color=discord.Color.red()),
                delete_after=5
            )

        q = list(player.queue)
        # -1 means last added (end of queue)
        target = len(q) - 1 if index == -1 else index - 1

        if target < 0 or target >= len(q):
            return await ctx.send(
                embed=discord.Embed(
                    description=f"❌ Invalid position. Queue has {len(q)} song(s).",
                    color=discord.Color.red()
                ),
                delete_after=5
            )

        removed = q.pop(target)
        from collections import deque
        player.queue = deque(q)

        await ctx.send(
            embed=discord.Embed(
                description=f"🗑️ Removed **{removed['title']}** from the queue.",
                color=PINK
            ),
            delete_after=5
        )
        try: await ctx.message.delete()
        except Exception: pass

    # ── $search ───────────────────────────────────────────────────

    @commands.command(name="search", aliases=["find"])
    async def search(self, ctx: commands.Context, *, query: str):
        """Shows a dropdown of 5 YouTube results to pick from."""

        # No query = show music help
        if not query:
            embed = discord.Embed(
                title="🎵  Lumi Music — Commands",
                description="Play music from YouTube directly in your voice channel!",
                color=PINK
            )
            embed.add_field(
                name="▶️  Play",
                value="""`$play <song name or URL>` — Play a song or add to queue
`$search <query>` — Pick from 5 search results""",
                inline=False
            )
            embed.add_field(
                name="⏯️  Controls",
                value="""`$skip` / `$s` — Skip current song
`$pause` / `$resume` — Toggle pause
`$remove` — Remove last queued song
`$remove <#>` — Remove song at position""",
                inline=False
            )
            embed.add_field(
                name="🎛️  Button Controls",
                value="""⏮ Previous  🔁 Loop  ⏸ Pause  🔀 Shuffle  ⏭ Skip
🔉 Volume−  📋 Queue  ⏹ Stop  🔊 Volume+""",
                inline=False
            )
            embed.add_field(
                name="💡  Tips",
                value="""• Works with song names, YouTube URLs, or search terms
• Queue songs while one is already playing
• Controls always move to the latest message""",
                inline=False
            )
            embed.set_footer(text="Example: $play never gonna give you up")
            return await ctx.send(embed=embed)

        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send(
                embed=discord.Embed(description="❌ Join a voice channel first!", color=discord.Color.red()),
                delete_after=5
            )

        try: await ctx.message.delete()
        except Exception: pass

        searching = await ctx.send(
            embed=discord.Embed(description=f"🔍 Searching for **{query}**...", color=PINK)
        )

        results = await search_tracks(query, limit=5)
        if not results:
            return await searching.edit(
                embed=discord.Embed(description="❌ No results found!", color=discord.Color.red())
            )

        lines = [
            f"`{i}.` **{r['title'][:60]}** · {format_duration(r['duration'])}"
            for i, r in enumerate(results, start=1)
        ]
        embed = discord.Embed(
            title=f"🔍  Results for \"{query}\"",
            description="\n".join(lines),
            color=PINK
        )
        embed.set_footer(text="Select a song below • Expires in 30 seconds")
        view = SearchView(self, results, ctx.author.display_name)
        await searching.edit(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
