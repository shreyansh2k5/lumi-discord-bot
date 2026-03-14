# music/ytdl.py
# Primary: pytubefix (Innertube API)
# Fallback: yt-dlp with cookies

import asyncio
import os
import shutil
from pathlib import Path
from http.cookiejar import MozillaCookieJar

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


# ── pytubefix ─────────────────────────────────────────────────────

def _pytube_stream_sync(url: str) -> dict | None:
    """Fetch a fresh stream URL via pytubefix right before playing."""
    try:
        from pytubefix import YouTube
        yt = YouTube(url, use_oauth=False, allow_oauth_cache=False, client="TV")
        title = yt.title
        stream = yt.streams.filter(only_audio=True).order_by("abr").last()
        if not stream:
            # Try any stream if audio-only not available
            stream = yt.streams.filter(progressive=True).order_by("resolution").last()
        if not stream:
            print(f"[Music] pytubefix: no stream for {url}")
            return None
        print(f"[Music] ✅ pytubefix: {title}")
        return {
            "title":       title,
            "url":         stream.url,
            "webpage_url": yt.watch_url,
            "duration":    yt.length or 0,
            "thumbnail":   yt.thumbnail_url or "",
            "uploader":    yt.author or "Unknown",
        }
    except Exception as e:
        print(f"[Music] pytubefix error: {type(e).__name__}: {e}")
        return None


def _pytube_search_sync(query: str, limit: int = 5) -> list[dict]:
    try:
        from pytubefix import Search
        s = Search(query)
        results = []
        for v in s.videos[:limit]:
            try:
                results.append({
                    "title":       v.title,
                    "webpage_url": v.watch_url,
                    "video_id":    v.video_id,
                    "duration":    v.length or 0,
                    "uploader":    v.author or "Unknown",
                    "thumbnail":   v.thumbnail_url or "",
                })
            except Exception:
                continue
        return results
    except Exception as e:
        print(f"[Music] pytubefix search error: {e}")
        return []


# ── yt-dlp fallback ───────────────────────────────────────────────

def _ytdlp_sync(query: str) -> dict | None:
    try:
        import yt_dlp
        opts = {
            "format":         "bestaudio/best",
            "noplaylist":     True,
            "quiet":          True,
            "no_warnings":    True,
            "default_search": "ytsearch",
            "source_address": "0.0.0.0",
            "extract_flat":   False,
        }
        if _has_cookies:
            opts["cookiefile"] = str(_COOKIES_FILE)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if not info:
                return None
            if "entries" in info:
                info = info["entries"][0]
            return {
                "title":       info.get("title", "Unknown"),
                "url":         info.get("url") or info.get("webpage_url"),
                "webpage_url": info.get("webpage_url", ""),
                "duration":    info.get("duration", 0),
                "thumbnail":   info.get("thumbnail", ""),
                "uploader":    info.get("uploader", "Unknown"),
            }
    except Exception as e:
        print(f"[Music] yt-dlp error: {e}")
        return None


# ── Public API ────────────────────────────────────────────────────

async def fetch_track(query: str) -> dict | None:
    """
    Fetch track info. For direct URLs uses pytubefix directly.
    For search queries, searches first then fetches the stream.
    Always returns a fresh stream URL.
    """
    loop = asyncio.get_event_loop()

    if query.startswith("http"):
        result = await loop.run_in_executor(None, _pytube_stream_sync, query)
        if result:
            return result
        return await loop.run_in_executor(None, _ytdlp_sync, query)

    # Search first
    results = await loop.run_in_executor(None, _pytube_search_sync, query, 1)
    if results:
        result = await loop.run_in_executor(None, _pytube_stream_sync, results[0]["webpage_url"])
        if result:
            return result

    return await loop.run_in_executor(None, _ytdlp_sync, query)


async def refresh_track_url(track: dict) -> dict:
    """
    Re-fetches a fresh stream URL for a track before playing.
    pytubefix URLs expire — always call this right before FFmpeg starts.
    """
    if not track.get("webpage_url"):
        return track
    loop = asyncio.get_event_loop()
    fresh = await loop.run_in_executor(None, _pytube_stream_sync, track["webpage_url"])
    if fresh:
        track["url"] = fresh["url"]
    return track


async def search_tracks(query: str, limit: int = 5) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _pytube_search_sync, query, limit)


def format_duration(seconds: int) -> str:
    if not seconds:
        return "Live"
    h, rem = divmod(int(seconds), 3600)
    m, s   = divmod(rem, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"
