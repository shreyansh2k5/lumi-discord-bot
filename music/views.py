# music/views.py
import discord
from core.embeds import PINK
from music.ytdl import format_duration


class MusicControlView(discord.ui.View):
    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=None)
        self.cog      = cog
        self.guild_id = guild_id

    def _p(self):
        from music.player import get_player
        return get_player(self.guild_id)

    async def _refresh(self, interaction: discord.Interaction):
        p = self._p()
        if p and p.current:
            from music.embeds import build_np_embed
            embed = build_np_embed(p.current, len(p.queue), p.paused, p.loop, p.volume_pct)
            try: await interaction.response.edit_message(embed=embed, view=self)
            except Exception: await interaction.response.defer()
        else:
            try:
                await interaction.response.edit_message(
                    embed=discord.Embed(description="⏹ Playback stopped.", color=PINK), view=None)
            except Exception: await interaction.response.defer()

    @discord.ui.button(emoji="⏮", style=discord.ButtonStyle.secondary, row=0)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._p()
        if not p or not p.current:
            return await interaction.response.send_message("Nothing playing!", ephemeral=True)
        p.queue.appendleft(p.current)
        p.queue.appendleft(p.current)
        p.skip()
        await interaction.response.defer()

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=0)
    async def btn_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._p()
        if not p: return await interaction.response.send_message("Nothing playing!", ephemeral=True)
        p.loop = not p.loop
        button.style = discord.ButtonStyle.success if p.loop else discord.ButtonStyle.secondary
        await self._refresh(interaction)

    @discord.ui.button(emoji="⏸", style=discord.ButtonStyle.primary, row=0)
    async def btn_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._p()
        if not p: return await interaction.response.send_message("Nothing playing!", ephemeral=True)
        paused = p.toggle_pause()
        button.emoji = discord.PartialEmoji(name="▶" if paused else "⏸")
        button.style = discord.ButtonStyle.secondary if paused else discord.ButtonStyle.primary
        await self._refresh(interaction)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, row=0)
    async def btn_shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._p()
        if not p: return await interaction.response.send_message("Nothing playing!", ephemeral=True)
        q = list(p.queue)
        import random; random.shuffle(q)
        from collections import deque; p.queue = deque(q)
        await interaction.response.defer()

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.secondary, row=0)
    async def btn_skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._p()
        if not p: return await interaction.response.send_message("Nothing to skip!", ephemeral=True)
        p.skip()
        await interaction.response.defer()

    @discord.ui.button(emoji="📋", style=discord.ButtonStyle.secondary, row=1)
    async def btn_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._p()
        if not p or not p.queue:
            return await interaction.response.send_message("Queue is empty!", ephemeral=True)
        lines = [f"`{i}.` {t['title']} ({format_duration(t.get('duration',0))})"
                 for i, t in enumerate(list(p.queue)[:10], 1)]
        if len(p.queue) > 10: lines.append(f"*...and {len(p.queue)-10} more*")
        await interaction.response.send_message(
            embed=discord.Embed(title="📋  Queue", description="\n".join(lines), color=PINK),
            ephemeral=True)

    @discord.ui.button(emoji="🔉", style=discord.ButtonStyle.secondary, row=1)
    async def btn_vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._p()
        if not p: return await interaction.response.send_message("Nothing playing!", ephemeral=True)
        p.set_volume(-0.1)
        await self._refresh(interaction)

    @discord.ui.button(emoji="⏹", style=discord.ButtonStyle.danger, row=1)
    async def btn_stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._p()
        if not p: return await interaction.response.send_message("Nothing playing!", ephemeral=True)
        vc = p.vc
        from music.player import remove_player
        p.stop(); remove_player(self.guild_id)
        try: await vc.disconnect()
        except Exception: pass
        try:
            await interaction.response.edit_message(
                embed=discord.Embed(description="⏹ Stopped and disconnected.", color=PINK), view=None)
        except Exception: await interaction.response.defer()

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, row=1)
    async def btn_vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self._p()
        if not p: return await interaction.response.send_message("Nothing playing!", ephemeral=True)
        p.set_volume(0.1)
        await self._refresh(interaction)


class SearchSelect(discord.ui.Select):
    def __init__(self, cog, results: list, requester: str):
        self.cog       = cog
        self.results   = results
        self.requester = requester
        options = [
            discord.SelectOption(
                label=r["title"][:100],
                description=f"{format_duration(r.get('duration',0))} · {r.get('uploader','')[:40]}"[:100],
                value=str(i)
            ) for i, r in enumerate(results)
        ]
        super().__init__(placeholder="🎵 Pick a song...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        chosen = self.results[int(self.values[0])]
        await interaction.message.edit(
            embed=discord.Embed(description=f"⏳ Loading **{chosen['title']}**...", color=PINK), view=None)

        from music.ytdl import fetch_track
        track = await fetch_track(chosen["webpage_url"])
        if not track:
            return await interaction.followup.send("❌ Failed to load track.", ephemeral=True)
        track["requester"] = self.requester

        if not interaction.user.voice:
            return await interaction.followup.send("Join a voice channel first!", ephemeral=True)

        await self.cog._queue_or_play(interaction.guild, interaction.user.voice.channel,
                                       interaction.channel, track)
        await interaction.message.edit(
            embed=discord.Embed(description=f"✅ **{track['title']}** added!", color=PINK))


class SearchView(discord.ui.View):
    def __init__(self, cog, results: list, requester: str):
        super().__init__(timeout=30)
        self.add_item(SearchSelect(cog, results, requester))