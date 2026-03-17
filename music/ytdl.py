# music/ytdl.py
# Uses pytubefix (Innertube API) for YouTube — no cookies, no bot detection.
# Falls back to yt-dlp for non-YouTube URLs (SoundCloud etc).

import asyncio
import os
import shutil
from pathlib import Path

_ROOT = Path(__file__).parent.parent.resolve()


# ── FFmpeg path ───────────────────────────────────────────────────
# Call static_ffmpeg.add_paths() FIRST so it registers before we search

try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
    print("[Music] static-ffmpeg loaded")
except ImportError:
    pass

def _find_ffmpeg() -> str:
    # 1. Next to main.py (local Windows dev)
    local = _ROOT / "ffmpeg.exe"
    if local.exists():
        return str(local)
    # 2. System PATH (includes static-ffmpeg path after add_paths())
    found = shutil.which("ffmpeg")
    if found:
        return found
    # 3. Nix store (Railway)
    nix = "/nix/var/nix/profiles/default/bin/ffmpeg"
    if os.path.exists(nix):
        return nix
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


# ── YouTube via pytubefix (Innertube) ─────────────────────────────

def _build_yt_opts(extra: dict = {}) -> dict:
    """Build yt-dlp options, injecting cookies from file or env variable."""
    import tempfile
    opts = {
        "format":         "bestaudio/best",
        "noplaylist":     True,
        "quiet":          True,
        "no_warnings":    True,
        "default_search": "ytsearch",
        "source_address": "0.0.0.0",
        "extract_flat":   False,
        **extra,
    }
    # 1. cookies.txt file next to main.py
    cookies_file = _ROOT / "cookies.txt"
    if cookies_file.exists():
        opts["cookiefile"] = str(cookies_file)
        return opts
    # 2. YT_COOKIES env variable (multiline cookie content stored in Railway vars)
    cookies_env = os.getenv("YT_COOKIES", "")
    if cookies_env:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        tmp.write(cookies_env.replace("\n", "
"))
        tmp.flush()
        opts["cookiefile"] = tmp.name
        return opts
    return opts


def _yt_fetch_sync(query: str) -> dict | None:
    """Fetch YouTube audio using yt-dlp with cookies."""
    import yt_dlp
    opts = _build_yt_opts({"extractor_args": {"youtube": {"player_client": ["tv_embedded", "ios", "web"]}}})
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
            if "entries" in info:
                info = info["entries"][0]
            if not info.get("url"):
                return None
            print(f"[Music] ✅ Got stream")
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


def _yt_search_sync(query: str, limit: int) -> list[dict]:
    """Search YouTube using yt-dlp flat extract — no bot detection on metadata."""
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


# ── yt-dlp fallback for non-YouTube ──────────────────────────────

def _ytdlp_fetch_sync(query: str) -> dict | None:
    import yt_dlp
    opts = {
        "format":         "bestaudio/best",
        "noplaylist":     True,
        "quiet":          True,
        "no_warnings":    True,
        "default_search": "scsearch",
        "source_address": "0.0.0.0",
        "extract_flat":   False,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
            if "entries" in info:
                info = info["entries"][0]
            return {
                "title":       info.get("title",       "Unknown"),
                "url":         info.get("url") or info.get("webpage_url"),
                "webpage_url": info.get("webpage_url", ""),
                "duration":    info.get("duration",    0),
                "thumbnail":   info.get("thumbnail",   ""),
                "uploader":    info.get("uploader",    "Unknown"),
            }
        except Exception:
            return None


# ── Public async API ──────────────────────────────────────────────

async def fetch_track(query: str) -> dict | None:
    """Fetch a single track. Uses tv_embedded yt-dlp for YouTube, fallback for others."""
    loop = asyncio.get_event_loop()
    if _is_youtube(query) or not query.startswith("http"):
        return await loop.run_in_executor(None, _yt_fetch_sync, query)
    else:
        return await loop.run_in_executor(None, _ytdlp_fetch_sync, query)


async def search_tracks(query: str, limit: int = 5) -> list[dict]:
    """Search YouTube and return flat results for the dropdown."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _yt_search_sync, query, limit)