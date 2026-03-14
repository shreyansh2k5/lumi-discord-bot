# music/player.py
# Manages per-guild music state: queue, current track, loop, shuffle.
# One GuildPlayer instance per guild, stored in the module-level dict.

import random
from collections import deque
import discord

from music.ytdl import FFMPEG_OPTIONS, refresh_track_url


class GuildPlayer:
    """All music state for one guild."""

    def __init__(self, voice_client: discord.VoiceClient):
        self.voice_client: discord.VoiceClient = voice_client
        self.queue:        deque[dict]          = deque()
        self.current:      dict | None          = None
        self.loop:         bool                 = False
        self.shuffle:      bool                 = False
        self.volume:       float                = 1.0      # 0.0 – 2.0
        self.now_playing_message: discord.Message | None = None

    # ── Playback ─────────────────────────────────────────────────

    async def play_next(self, after_callback=None, after=None):
        """
        Plays the next track in the queue.
        If loop is on, re-queues the current track before popping.
        If shuffle is on, picks a random track.
        """
        if self.loop and self.current:
            self.queue.appendleft(self.current)

        if not self.queue:
            self.current = None
            return

        if self.shuffle and len(self.queue) > 1:
            idx  = random.randrange(len(self.queue))
            new_q = list(self.queue)
            track = new_q.pop(idx)
            self.queue = deque(new_q)
            self.current = track
        else:
            self.current = self.queue.popleft()

        # Refresh stream URL right before playing — pytubefix URLs expire
        self.current = await refresh_track_url(self.current)

        source = discord.FFmpegPCMAudio(self.current["url"], **FFMPEG_OPTIONS)
        source = discord.PCMVolumeTransformer(source, volume=self.volume)
        self.voice_client.play(source, after=after or after_callback)

    def skip(self):
        """Stops the current track — triggers after_callback which calls play_next."""
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()

    def stop(self):
        """Clears the queue and stops playback."""
        self.queue.clear()
        self.current = None
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()

    def toggle_pause(self) -> bool:
        """Toggles pause/resume. Returns True if now paused."""
        if self.voice_client.is_paused():
            self.voice_client.resume()
            return False
        elif self.voice_client.is_playing():
            self.voice_client.pause()
            return True
        return False

    def set_volume(self, delta: float):
        """Adjust volume by delta (-0.1 or +0.1). Clamps to 0.1–2.0."""
        self.volume = max(0.1, min(2.0, self.volume + delta))
        if self.voice_client.source and isinstance(self.voice_client.source, discord.PCMVolumeTransformer):
            self.voice_client.source.volume = self.volume

    @property
    def volume_percent(self) -> int:
        return int(self.volume * 100)

    @property
    def is_paused(self) -> bool:
        return self.voice_client.is_paused()

    @property
    def queue_list(self) -> list[dict]:
        return list(self.queue)


# ── Global registry ──────────────────────────────────────────────
# guild_id -> GuildPlayer
_players: dict[int, GuildPlayer] = {}


def get_player(guild_id: int) -> GuildPlayer | None:
    return _players.get(guild_id)


def create_player(guild_id: int, voice_client: discord.VoiceClient) -> GuildPlayer:
    player = GuildPlayer(voice_client)
    _players[guild_id] = player
    return player


def remove_player(guild_id: int):
    _players.pop(guild_id, None)
