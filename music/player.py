# music/player.py
import random
import os
import shutil
from collections import deque
import discord


# ── Resolve FFmpeg at runtime ─────────────────────────────────────

def _get_ffmpeg() -> str:
    # 1. static-ffmpeg package
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
        f = shutil.which("ffmpeg")
        if f:
            print(f"[Music] FFmpeg from static-ffmpeg: {f}")
            return f
    except ImportError:
        pass
    # 2. Common system paths (Railway / Linux)
    for p in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg",
              "/nix/var/nix/profiles/default/bin/ffmpeg",
              "/root/.nix-profile/bin/ffmpeg"]:
        if os.path.exists(p):
            print(f"[Music] FFmpeg at: {p}")
            return p
    # 3. Walk nix store (Railway nixpacks puts it here)
    try:
        import glob
        matches = glob.glob("/nix/store/*/bin/ffmpeg")
        if matches:
            print(f"[Music] FFmpeg in nix store: {matches[0]}")
            return matches[0]
    except Exception:
        pass
    # 4. Local Windows dev
    from pathlib import Path
    local = Path(__file__).parent.parent / "ffmpeg.exe"
    if local.exists():
        return str(local)
    print("[Music] ⚠️ FFmpeg not found!")
    return "ffmpeg"


_FFMPEG = _get_ffmpeg()

FFMPEG_OPTIONS = {
    "executable":     _FFMPEG,
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options":        "-vn",
}


# ── Guild player ──────────────────────────────────────────────────

class GuildPlayer:
    def __init__(self, vc: discord.VoiceClient):
        self.vc      = vc
        self.queue   = deque()
        self.current = None
        self.loop    = False
        self.volume  = 1.0
        self.np_msg  = None

    @property
    def paused(self):     return self.vc.is_paused()
    @property
    def playing(self):    return self.vc.is_playing()
    @property
    def volume_pct(self): return int(self.volume * 100)

    def play_next(self, after=None):
        if self.loop and self.current:
            self.queue.appendleft(self.current)
        if not self.queue:
            self.current = None
            return
        self.current = self.queue.popleft()
        src = discord.FFmpegPCMAudio(self.current["url"], **FFMPEG_OPTIONS)
        src = discord.PCMVolumeTransformer(src, volume=self.volume)
        self.vc.play(src, after=after)

    def skip(self):
        if self.vc.is_playing() or self.vc.is_paused():
            self.vc.stop()

    def stop(self):
        self.queue.clear()
        self.current = None
        if self.vc.is_playing() or self.vc.is_paused():
            self.vc.stop()

    def toggle_pause(self):
        if self.vc.is_paused():
            self.vc.resume(); return False
        elif self.vc.is_playing():
            self.vc.pause(); return True
        return False

    def set_volume(self, delta: float):
        self.volume = max(0.1, min(2.0, self.volume + delta))
        if isinstance(self.vc.source, discord.PCMVolumeTransformer):
            self.vc.source.volume = self.volume


_players: dict[int, GuildPlayer] = {}

def get_player(gid):    return _players.get(gid)
def remove_player(gid): _players.pop(gid, None)
def create_player(gid, vc):
    p = GuildPlayer(vc)
    _players[gid] = p
    return p