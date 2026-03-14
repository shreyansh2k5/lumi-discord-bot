# music/ytdl.py

import asyncio
import os
import shutil
from pathlib import Path
import yt_dlp

# ── FFmpeg path ───────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent.resolve()

def _find_ffmpeg() -> str:
    local = _ROOT / "ffmpeg.exe"
    if local.exists():
        return str(local)
    found = shutil.which("ffmpeg")
    if found:
        return found
    nix_path = "/nix/var/nix/profiles/default/bin/ffmpeg"
    if os.path.exists(nix_path):
        return nix_path
    return "ffmpeg"

FFMPEG_EXECUTABLE = _find_ffmpeg()
print(f"[Music] FFmpeg: {FFMPEG_EXECUTABLE}")

# ── Cookies ───────────────────────────────────────────────────────
_COOKIES_FILE = _ROOT / "cookies.txt"
_has_cookies  = _COOKIES_FILE.exists()
if not _has_cookies:
    _alt = Path("/app/cookies.txt")
    if _alt.exists():
        _COOKIES_FILE = _alt
        _has_cookies  = True
print(f"[Music] Cookies: {'✅ ' + str(_COOKIES_FILE) if _has_cookies else '❌ not found'}")

# ── yt-dlp options ────────────────────────────────────────────────
# android client is most reliable — no format restrictions, no bot check
_COOKIE_OPTS = {"cookiefile": str(_COOKIES_FILE)} if _has_cookies else {}

YTDL_OPTIONS = {
    "format":         "bestaudio/best",
    "noplaylist":     True,
    "quiet":          True,
    "no_warnings":    True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "extract_flat":   False,
    "extractor_args": {
        "youtube": {
            # ios client bypasses signature challenge — no JS needed
            "player_client": ["ios", "android"],
        }
    },
    **_COOKIE_OPTS,
}

YTDL_OPTIONS_SEARCH = {
    "format":         "bestaudio",
    "noplaylist":     True,
    "quiet":          True,
    "no_warnings":    True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "extract_flat":   True,
    "extractor_args": {
        "youtube": {"player_client": ["android"]}
    },
    **_COOKIE_OPTS,
}

FFMPEG_OPTIONS = {
    "executable":     FFMPEG_EXECUTABLE,
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options":        "-vn",
}


def _extract_sync(query: str) -> dict | None:
    with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
        except Exception as e:
            print(f"[Music] Extract error: {e}")
            return None
        if not info:
            return None
        if "entries" in info:
            info = info["entries"][0]
        # Re-extract full info if we only got a flat entry
        if not info.get("url"):
            try:
                info = ydl.extract_info(info.get("webpage_url") or info.get("id"), download=False)
            except Exception as e:
                print(f"[Music] Re-extract error: {e}")
                return None
        return {
            "title":       info.get("title",    "Unknown Title"),
            "url":         info.get("url") or info.get("webpage_url"),
            "webpage_url": info.get("webpage_url", ""),
            "duration":    info.get("duration",  0),
            "thumbnail":   info.get("thumbnail", ""),
            "uploader":    info.get("uploader",  "Unknown"),
        }


async def fetch_track(query: str) -> dict | None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _extract_sync, query)


def format_duration(seconds: int) -> str:
    if not seconds:
        return "Live"
    h, rem = divmod(int(seconds), 3600)
    m, s   = divmod(rem, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


async def search_tracks(query: str, limit: int = 5) -> list[dict]:
    def _search():
        with yt_dlp.YoutubeDL(YTDL_OPTIONS_SEARCH) as ydl:
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
            except Exception as e:
                print(f"[Music] Search error: {e}")
                return []
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _search)
