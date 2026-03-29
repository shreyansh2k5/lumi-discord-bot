# cogs/music.py — Lavalink via wavelink, local server + public fallbacks
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import wavelink

from music.nodes  import LAVALINK_NODES
from music.embeds import build_np_embed, format_duration
from core.embeds  import PINK


def _connected_node() -> wavelink.Node | None:
    """Returns the first connected node, or None."""
    try:
        for node in wavelink.Pool.nodes.values():
            if node.status == wavelink.NodeStatus.CONNECTED:
                return node
    except Exception:
        pass
    return None


# ── Control view ──────────────────────────────────────────────────

class MusicControlView(discord.ui.View):
    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=None)
        self.cog      = cog
        self.guild_id = guild_id

    def _player(self) -> wavelink.Player | None:
        guild = self.cog.bot.get_guild(self.guild_id)
        return guild.voice_client if guild else None

    async def _refresh(self, interaction: discord.Interaction):
        p = self._player()
        if p and p.current:
            try:
                await interaction.response.edit_message(embed=build_np_embed(p), view=self)
            except Exception:
                await interaction.response.defer()
        else:
            try:
                await interaction.response.edit_message(
                    embed=discord.Embed(description="⏹ Stopped.", color=PINK), view=None)
            except Exception:
                await interaction.response.defer()

    @discord.ui.button(emoji="⏮", style=discord.ButtonStyle.secondary, row=0)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._player()
        if not p: return await interaction.response.send_message("Nothing playing!", ephemeral=True)
        try: await p.seek(0)
        except Exception: pass
        await interaction.response.defer()

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=0)
    async def btn_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._player()
        if not p: return await interaction.response.send_message("Nothing playing!", ephemeral=True)
        if p.queue.mode == wavelink.QueueMode.loop:
            p.queue.mode = wavelink.QueueMode.normal
            button.style = discord.ButtonStyle.secondary
        else:
            p.queue.mode = wavelink.QueueMode.loop
            button.style = discord.ButtonStyle.success
        await self._refresh(interaction)

    @discord.ui.button(emoji="⏸", style=discord.ButtonStyle.primary, row=0)
    async def btn_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._player()
        if not p: return await interaction.response.send_message("Nothing playing!", ephemeral=True)
        await p.pause(not p.paused)
        button.emoji = discord.PartialEmoji(name="▶" if p.paused else "⏸")
        button.style = discord.ButtonStyle.secondary if p.paused else discord.ButtonStyle.primary
        await self._refresh(interaction)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, row=0)
    async def btn_shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._player()
        if not p: return await interaction.response.send_message("Nothing playing!", ephemeral=True)
        p.queue.shuffle()
        await interaction.response.defer()

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.secondary, row=0)
    async def btn_skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._player()
        if not p: return await interaction.response.send_message("Nothing to skip!", ephemeral=True)
        await p.skip(force=True)
        await interaction.response.defer()

    @discord.ui.button(emoji="📋", style=discord.ButtonStyle.secondary, row=1)
    async def btn_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._player()
        if not p or p.queue.is_empty:
            return await interaction.response.send_message("Queue is empty!", ephemeral=True)
        lines = [f"`{i}.` {t.title} ({format_duration(t.length)})"
                 for i, t in enumerate(list(p.queue)[:10], 1)]
        if len(p.queue) > 10:
            lines.append(f"*...and {len(p.queue) - 10} more*")
        await interaction.response.send_message(
            embed=discord.Embed(title="📋  Queue", description="\n".join(lines), color=PINK),
            ephemeral=True)

    @discord.ui.button(emoji="🔉", style=discord.ButtonStyle.secondary, row=1)
    async def btn_vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._player()
        if not p: return await interaction.response.send_message("Nothing playing!", ephemeral=True)
        await p.set_volume(max(10, p.volume - 10))
        await self._refresh(interaction)

    @discord.ui.button(emoji="⏹", style=discord.ButtonStyle.danger, row=1)
    async def btn_stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._player()
        if not p: return await interaction.response.send_message("Nothing playing!", ephemeral=True)
        self.cog.np_msgs.pop(self.guild_id, None)
        await p.disconnect()
        try:
            await interaction.response.edit_message(
                embed=discord.Embed(description="⏹ Stopped and disconnected.", color=PINK), view=None)
        except Exception:
            await interaction.response.defer()

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, row=1)
    async def btn_vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._player()
        if not p: return await interaction.response.send_message("Nothing playing!", ephemeral=True)
        await p.set_volume(min(200, p.volume + 10))
        await self._refresh(interaction)


# ── Search ────────────────────────────────────────────────────────

class SearchSelect(discord.ui.Select):
    def __init__(self, cog, tracks: list, requester: str):
        self.cog       = cog
        self.tracks    = tracks
        self.requester = requester
        options = [
            discord.SelectOption(
                label=t.title[:100],
                description=f"{format_duration(t.length)} · {t.author[:40]}"[:100],
                value=str(i)
            ) for i, t in enumerate(tracks)
        ]
        super().__init__(placeholder="🎵 Pick a song...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        track = self.tracks[int(self.values[0])]
        track.extras = wavelink.ExtrasNamespace({"requester": interaction.user.display_name})
        await interaction.message.edit(
            embed=discord.Embed(description=f"✅ **{track.title}** added!", color=PINK), view=None)
        if not interaction.user.voice:
            return await interaction.followup.send("Join a voice channel first!", ephemeral=True)
        await self.cog._queue_or_play(
            interaction.guild, interaction.user.voice.channel, interaction.channel, track)


class SearchView(discord.ui.View):
    def __init__(self, cog, tracks: list, requester: str):
        super().__init__(timeout=30)
        self.add_item(SearchSelect(cog, tracks, requester))


# ── Music Cog ─────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self.np_msgs: dict[int, discord.Message] = {}

    async def cog_load(self):
        asyncio.create_task(self._connect_nodes())

    async def _connect_nodes(self):
        """
        Tries every node in order.
        Stops at the first successful connection.
        Retries all nodes every 60s if all fail.
        """
        await self.bot.wait_until_ready()
        while True:
            for n in LAVALINK_NODES:
                try:
                    # Skip if already connected to this node
                    existing = wavelink.Pool.nodes.get(n.get("name", n["uri"]))
                    if existing and existing.status == wavelink.NodeStatus.CONNECTED:
                        print(f"[Music] Already connected to {n['uri']}")
                        return

                    node = wavelink.Node(uri=n["uri"], password=n["password"])
                    await wavelink.Pool.connect(
                        nodes=[node], client=self.bot, cache_capacity=100)
                    print(f"[Music] ✅ Connected: {n['uri']}")
                    return
                except Exception as e:
                    print(f"[Music] ❌ {n['uri']} — {e}")
                    continue

            print("[Music] ⚠️ All nodes failed. Retrying in 60s...")
            await asyncio.sleep(60)

    async def _get_player(self, guild, vc_channel) -> wavelink.Player:
        player: wavelink.Player = guild.voice_client
        if not player:
            player = await vc_channel.connect(cls=wavelink.Player, self_deaf=True)
            player.autoplay = wavelink.AutoPlayMode.disabled
        elif player.channel != vc_channel:
            await player.move_to(vc_channel)
        return player

    async def _send_np(self, guild_id: int, player: wavelink.Player, channel: discord.TextChannel):
        old = self.np_msgs.get(guild_id)
        if old:
            try: await old.delete()
            except Exception: pass
        embed = build_np_embed(player)
        view  = MusicControlView(self, guild_id)
        self.np_msgs[guild_id] = await channel.send(embed=embed, view=view)

    async def _queue_or_play(self, guild, vc_channel, channel, track):
        player   = await self._get_player(guild, vc_channel)
        guild_id = guild.id

        if player.playing or player.paused:
            await player.queue.put_wait(track)
            pos   = len(player.queue)
            embed = discord.Embed(
                title="📋  Added to Queue",
                description=f"**{track.title}**\n⏱ {format_duration(track.length)} · Position #{pos}",
                color=PINK)
            if track.artwork:
                embed.set_thumbnail(url=track.artwork)
            msg = await channel.send(embed=embed)
            await self._send_np(guild_id, player, channel)
            try: await msg.delete(delay=5)
            except Exception: pass
        else:
            await player.play(track)
            await asyncio.sleep(0.5)
            await self._send_np(guild_id, player, channel)

    # ── Wavelink events ───────────────────────────────────────────

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f"[Music] ✅ Node ready: {payload.node.uri}")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player = payload.player
        if not player:
            return
        guild_id = player.guild.id
        np       = self.np_msgs.get(guild_id)
        channel  = np.channel if np else None

        if not player.queue.is_empty:
            track = await player.queue.get_wait()
            await player.play(track)
            if channel:
                await self._send_np(guild_id, player, channel)
        else:
            if np:
                try:
                    await np.edit(
                        embed=discord.Embed(description="✅ Queue finished!", color=PINK),
                        view=None)
                except Exception:
                    pass
            self.np_msgs.pop(guild_id, None)
            await asyncio.sleep(2)
            try: await player.disconnect()
            except Exception: pass

    @commands.Cog.listener()
    async def on_wavelink_node_closed(self, payload: wavelink.NodeClosedEventPayload):
        print(f"[Music] ⚠️ Node disconnected: {payload.node.uri} — attempting reconnect...")
        asyncio.create_task(self._connect_nodes())

    # ── Commands ──────────────────────────────────────────────────

    @commands.hybrid_command(name="play", description="Play a song from YouTube 🎵")
    @app_commands.describe(query="Song name or YouTube URL")
    async def play(self, ctx: commands.Context, *, query: str = None):
        if not query:
            embed = discord.Embed(title="🎵  Lumi Music — Commands", color=PINK)
            embed.add_field(name="▶️  Play",     value="`$play <song/URL>`\n`$search <query>`", inline=False)
            embed.add_field(name="⏯️  Controls", value="`$skip` `$pause` `$resume` `$remove`",  inline=False)
            embed.add_field(name="🎛️  Buttons",  value="⏮ 🔁 ⏸ 🔀 ⏭ · 📋 🔉 ⏹ 🔊",           inline=False)
            embed.set_footer(text="Example: $play never gonna give you up")
            return await ctx.send(embed=embed)

        if not ctx.author.voice:
            return await ctx.send(embed=discord.Embed(
                description="❌ Join a voice channel first!", color=discord.Color.red()), ephemeral=True)

        if not _connected_node():
            return await ctx.send(embed=discord.Embed(
                description="⏳ Music service is connecting, try again in a moment!", color=discord.Color.orange()))

        await ctx.typing()
        if ctx.interaction is None:
            try: await ctx.message.delete()
            except Exception: pass

        tracks = await wavelink.Playable.search(query)
        if not tracks:
            return await ctx.send(embed=discord.Embed(
                description="❌ No results found!", color=discord.Color.red()))

        track = tracks[0]
        track.extras = wavelink.ExtrasNamespace({"requester": ctx.author.display_name})
        await self._queue_or_play(ctx.guild, ctx.author.voice.channel, ctx.channel, track)

    @commands.command(name="skip", aliases=["s"])
    async def skip(self, ctx: commands.Context):
        p: wavelink.Player = ctx.guild.voice_client
        if not p or not p.current:
            return await ctx.send(embed=discord.Embed(
                description="❌ Nothing playing!", color=discord.Color.red()), delete_after=5)
        title = p.current.title
        await p.skip(force=True)
        await ctx.send(embed=discord.Embed(
            description=f"⏭ Skipped **{title}**", color=PINK), delete_after=5)
        try: await ctx.message.delete()
        except Exception: pass

    @commands.command(name="pause", aliases=["resume"])
    async def pause(self, ctx: commands.Context):
        p: wavelink.Player = ctx.guild.voice_client
        if not p or not p.current:
            return await ctx.send(embed=discord.Embed(
                description="❌ Nothing playing!", color=discord.Color.red()), delete_after=5)
        await p.pause(not p.paused)
        label = "⏸ Paused" if p.paused else "▶ Resumed"
        await ctx.send(embed=discord.Embed(
            description=f"{label} **{p.current.title}**", color=PINK), delete_after=5)
        try: await ctx.message.delete()
        except Exception: pass

    @commands.command(name="remove")
    async def remove(self, ctx: commands.Context, index: int = -1):
        p: wavelink.Player = ctx.guild.voice_client
        if not p or p.queue.is_empty:
            return await ctx.send(embed=discord.Embed(
                description="❌ Queue is empty!", color=discord.Color.red()), delete_after=5)
        q      = list(p.queue)
        target = len(q) - 1 if index == -1 else index - 1
        if target < 0 or target >= len(q):
            return await ctx.send(embed=discord.Embed(
                description=f"❌ Invalid. Queue has {len(q)} song(s).", color=discord.Color.red()), delete_after=5)
        removed = q.pop(target)
        p.queue.clear()
        for t in q:
            await p.queue.put_wait(t)
        await ctx.send(embed=discord.Embed(
            description=f"🗑️ Removed **{removed.title}**", color=PINK), delete_after=5)
        try: await ctx.message.delete()
        except Exception: pass

    @commands.command(name="search", aliases=["find"])
    async def search(self, ctx: commands.Context, *, query: str):
        if not ctx.author.voice:
            return await ctx.send(embed=discord.Embed(
                description="❌ Join a voice channel first!", color=discord.Color.red()), delete_after=5)
        if not _connected_node():
            return await ctx.send(embed=discord.Embed(
                description="⏳ Music service connecting, try again in a moment!", color=discord.Color.orange()))
        try: await ctx.message.delete()
        except Exception: pass
        msg = await ctx.send(embed=discord.Embed(
            description=f"🔍 Searching **{query}**...", color=PINK))
        tracks = await wavelink.Playable.search(query)
        if not tracks:
            return await msg.edit(embed=discord.Embed(
                description="❌ No results found.", color=discord.Color.red()))
        results = tracks[:5]
        lines   = [f"`{i}.` **{t.title[:60]}** · {format_duration(t.length)}"
                   for i, t in enumerate(results, 1)]
        embed   = discord.Embed(title=f"🔍  \"{query}\"", description="\n".join(lines), color=PINK)
        embed.set_footer(text="Pick a song below • 30s to choose")
        await msg.edit(embed=embed, view=SearchView(self, results, ctx.author.display_name))


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))