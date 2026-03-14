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
print(f"[Music] Looking for cookies at: {_COOKIES_FILE}")
if _has_cookies:
    print(f"[Music] ✅ cookies.txt found!")
else:
    print(f"[Music] ❌ cookies.txt NOT found — YouTube may block requests")
    _alt = Path("/app/cookies.txt")
    if _alt.exists():
        _COOKIES_FILE = _alt
        _has_cookies  = True
        print(f"[Music] ✅ Found at fallback: {_alt}")

# ── yt-dlp options ────────────────────────────────────────────────
YTDL_OPTIONS = {
    "format":         "bestaudio/best",
    "noplaylist":     True,
    "quiet":          True,
    "no_warnings":    True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "extract_flat":   False,
    "extractor_args": {"youtube": {"player_client": ["web"]}},
    **( {"cookiefile": str(_COOKIES_FILE)} if _has_cookies else {} ),
}

YTDL_OPTIONS_SEARCH = {**YTDL_OPTIONS, "extract_flat": True}

FFMPEG_OPTIONS = {
    "executable":     FFMPEG_EXECUTABLE,
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options":        "-vn",
}


def _extract_sync(query: str) -> dict | None:
    with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
        except yt_dlp.utils.DownloadError:
            return None
        if "entries" in info:
            info = info["entries"][0]
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
            except Exception:
                return []
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _search)
