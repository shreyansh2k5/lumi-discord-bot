# music/ytdl.py
# Wraps yt-dlp to search YouTube and extract audio stream URLs.
# Returns plain dicts — no Discord imports here.

import asyncio
import os
from pathlib import Path
import yt_dlp

# ── FFmpeg path ───────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent.resolve()

def _find_ffmpeg() -> str:
    import shutil
    # 1. Next to main.py (local Windows dev)
    local = _ROOT / "ffmpeg.exe"
    if local.exists():
        return str(local)
    # 2. System PATH (Railway / Linux after nixpacks installs it)
    found = shutil.which("ffmpeg")
    if found:
        return found
    # 3. Common nix store location on Railway
    nix_path = "/nix/var/nix/profiles/default/bin/ffmpeg"
    if os.path.exists(nix_path):
        return nix_path
    return "ffmpeg"  # last resort, will error clearly if missing

FFMPEG_EXECUTABLE = _find_ffmpeg()
print(f"[Music] FFmpeg: {FFMPEG_EXECUTABLE}")

# yt-dlp options — audio only, no download, best quality
YTDL_OPTIONS = {
    "format":            "bestaudio/best",
    "noplaylist":        True,
    "quiet":             True,
    "no_warnings":       True,
    "default_search":    "ytsearch",   # treat bare text as a search query
    "source_address":    "0.0.0.0",    # bind to all interfaces
    "extract_flat":      False,
}

FFMPEG_OPTIONS = {
    "executable":     FFMPEG_EXECUTABLE,
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options":        "-vn",  # no video
}


def _extract_sync(query: str) -> dict | None:
    """Runs yt-dlp synchronously. Called via run_in_executor."""
    with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
        except yt_dlp.utils.DownloadError:
            return None

        # If it's a search result, take the first entry
        if "entries" in info:
            info = info["entries"][0]

        return {
            "title":     info.get("title",    "Unknown Title"),
            "url":       info.get("url")  or info.get("webpage_url"),
            "webpage_url": info.get("webpage_url", ""),
            "duration":  info.get("duration",  0),   # seconds
            "thumbnail": info.get("thumbnail", ""),
            "uploader":  info.get("uploader",  "Unknown"),
        }


async def fetch_track(query: str) -> dict | None:
    """
    Async wrapper — offloads yt-dlp to a thread so the bot loop isn't blocked.
    `query` can be a YouTube URL or plain search text.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _extract_sync, query)


def format_duration(seconds: int) -> str:
    """Converts seconds → m:ss or h:mm:ss string."""
    if not seconds:
        return "Live"
    h, rem = divmod(int(seconds), 3600)
    m, s   = divmod(rem, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


async def search_tracks(query: str, limit: int = 5) -> list[dict]:
    """Returns up to `limit` search results as a list of track dicts."""
    def _search():
        opts = {**YTDL_OPTIONS, "extract_flat": True, "quiet": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                results = []
                for entry in info.get("entries", [])[:limit]:
                    results.append({
                        "title":       entry.get("title", "Unknown"),
                        "webpage_url": entry.get("url") or entry.get("webpage_url", ""),
                        "duration":    entry.get("duration", 0),
                        "uploader":    entry.get("uploader", "Unknown"),
                        "thumbnail":   entry.get("thumbnail", ""),
                    })
                return results
            except Exception:
                return []
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _search)
