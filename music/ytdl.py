# music/ytdl.py

import asyncio
import os
import shutil
from pathlib import Path
import yt_dlp

# ── FFmpeg ────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent.resolve()

def _find_ffmpeg() -> str:
    local = _ROOT / "ffmpeg.exe"
    if local.exists():
        return str(local)
    found = shutil.which("ffmpeg")
    if found:
        return found
    if os.path.exists("/usr/bin/ffmpeg"):
        return "/usr/bin/ffmpeg"
    return "ffmpeg"

FFMPEG_EXECUTABLE = _find_ffmpeg()
print(f"[Music] FFmpeg: {FFMPEG_EXECUTABLE}")

FFMPEG_OPTIONS = {
    "executable":     FFMPEG_EXECUTABLE,
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options":        "-vn",
}

# ── Cookies ───────────────────────────────────────────────────────
_COOKIES_FILE = _ROOT / "cookies.txt"
if not _COOKIES_FILE.exists():
    _alt = Path("/app/cookies.txt")
    if _alt.exists():
        _COOKIES_FILE = _alt
_has_cookies = _COOKIES_FILE.exists()
print(f"[Music] Cookies: {'✅ ' + str(_COOKIES_FILE) if _has_cookies else '❌ not found'}")

# ── yt-dlp options ────────────────────────────────────────────────
_COOKIE_OPTS = {"cookiefile": str(_COOKIES_FILE)} if _has_cookies else {}

YTDL_OPTIONS = {
    "format":            "bestaudio[acodec!=none]/bestaudio/best[acodec!=none]/best",
    "noplaylist":        True,
    "quiet":             False,
    "no_warnings":       False,
    "verbose":           True,
    "default_search":    "ytsearch",
    "source_address":    "0.0.0.0",
    "extract_flat":      False,
    **_COOKIE_OPTS,
}

YTDL_SEARCH = {**YTDL_OPTIONS, "extract_flat": True}


def _extract_sync(query: str) -> dict | None:
    with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
        except Exception as e:
            print(f"[Music] yt-dlp error: {e}")
            return None
        if not info:
            return None
        if "entries" in info:
            info = info["entries"][0]
        if not info.get("url"):
            try:
                info = ydl.extract_info(info.get("webpage_url") or info.get("id"), download=False)
            except Exception as e:
                print(f"[Music] re-extract error: {e}")
                return None
        print(f"[Music] Got track: {info.get('title')}")
        return {
            "title":       info.get("title",    "Unknown"),
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
        with yt_dlp.YoutubeDL(YTDL_SEARCH) as ydl:
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
                print(f"[Music] search error: {e}")
                return []
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _search)
