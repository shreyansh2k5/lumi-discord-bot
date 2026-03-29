# music/ytdl.py
import asyncio
import os
import shutil
from pathlib import Path

_ROOT = Path(__file__).parent.parent.resolve()

# ── FFmpeg ────────────────────────────────────────────────────────

def _find_ffmpeg() -> str:
    # System PATH (installed via apt on Linux)
    found = shutil.which("ffmpeg")
    if found:
        return found
    # Local Windows dev
    local = _ROOT / "ffmpeg.exe"
    if local.exists():
        return str(local)
    return "ffmpeg"

FFMPEG_EXECUTABLE = _find_ffmpeg()
print(f"[Music] FFmpeg: {FFMPEG_EXECUTABLE}")

FFMPEG_OPTIONS = {
    "executable":     FFMPEG_EXECUTABLE,
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options":        "-vn",
}

# ── Helpers ───────────────────────────────────────────────────────

def _is_youtube(query: str) -> bool:
    return any(x in query for x in ("youtube.com", "youtu.be", "music.youtube.com"))

def format_duration(seconds: int) -> str:
    if not seconds:
        return "Live"
    h, rem = divmod(int(seconds), 3600)
    m, s   = divmod(rem, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"

# ── Cookie helper ─────────────────────────────────────────────────

def _get_cookie_opts() -> dict:
    import tempfile
    cookies_file = _ROOT / "cookies.txt"
    if cookies_file.exists():
        print("[Music] Using cookies.txt")
        return {"cookiefile": str(cookies_file)}
    cookies_env = os.getenv("YT_COOKIES", "")
    if cookies_env:
        import base64
        try:
            decoded = base64.b64decode(cookies_env.encode()).decode("utf-8")
        except Exception:
            decoded = cookies_env
        if not decoded.startswith("# Netscape"):
            decoded = "# Netscape HTTP Cookie File\n" + decoded
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        tmp.write(decoded)
        tmp.flush()
        print("[Music] Using YT_COOKIES env var")
        return {"cookiefile": tmp.name}
    return {}

# ── Fetch ─────────────────────────────────────────────────────────

def _fetch_sync(query: str) -> dict | None:
    import yt_dlp
    opts = {
        "format":         "bestaudio/best",
        "format_sort":    ["abr", "asr"],
        "noplaylist":     True,
        "quiet":          True,
        "no_warnings":    True,
        "default_search": "ytsearch",
        "source_address": "0.0.0.0",
        "extract_flat":   False,
        "extractor_args": {
            "youtube": {
                "player_client": ["tv_embedded", "ios", "web"]
            }
        },
        **_get_cookie_opts(),
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
            if "entries" in info:
                info = info["entries"][0]
            if not info.get("url"):
                return None
            return {
                "title":       info.get("title",       "Unknown"),
                "url":         info["url"],
                "webpage_url": info.get("webpage_url", ""),
                "duration":    info.get("duration",    0),
                "thumbnail":   info.get("thumbnail",   ""),
                "uploader":    info.get("uploader",    "Unknown"),
            }
        except Exception as e:
            print(f"[Music] fetch failed: {e}")
            return None

# ── Search ────────────────────────────────────────────────────────

def _search_sync(query: str, limit: int) -> list[dict]:
    import yt_dlp
    opts = {
        "quiet":          True,
        "no_warnings":    True,
        "extract_flat":   True,
        "default_search": "ytsearch",
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
            out  = []
            for e in info.get("entries", [])[:limit]:
                out.append({
                    "title":       e.get("title",    "Unknown"),
                    "webpage_url": f"https://www.youtube.com/watch?v={e['id']}",
                    "duration":    e.get("duration", 0),
                    "uploader":    e.get("uploader") or e.get("channel", "Unknown"),
                    "thumbnail":   e.get("thumbnail", ""),
                })
            return out
        except Exception as e:
            print(f"[Music] search error: {e}")
            return []

# ── Public async API ──────────────────────────────────────────────

async def fetch_track(query: str) -> dict | None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_sync, query)

async def search_tracks(query: str, limit: int = 5) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _search_sync, query, limit)