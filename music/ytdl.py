# music/ytdl.py
# Uses pytubefix (YouTube Innertube API) for stream URLs — no JS runtime needed.
# Falls back to yt-dlp for anything pytubefix can't handle.

import asyncio
import os
import shutil
from pathlib import Path

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


# ── pytubefix helpers ─────────────────────────────────────────────

def _pytube_search_sync(query: str, limit: int = 5) -> list[dict]:
    """Search YouTube via pytubefix Search."""
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
        print(f"[Music] pytubefix search: {len(results)} results")
        return results
    except Exception as e:
        print(f"[Music] pytubefix search error: {e}")
        return []


def _pytube_stream_sync(url_or_id: str) -> dict | None:
    """Get direct audio stream URL via pytubefix."""
    try:
        from pytubefix import YouTube
        from pytubefix.exceptions import AgeRestrictedError, VideoUnavailable
        if not url_or_id.startswith("http"):
            url_or_id = f"https://www.youtube.com/watch?v={url_or_id}"
        print(f"[Music] pytubefix fetching: {url_or_id}")
        yt = YouTube(url_or_id, use_oauth=False, allow_oauth_cache=False)
        print(f"[Music] pytubefix title: {yt.title}")
        streams = yt.streams.filter(only_audio=True).order_by("abr")
        print(f"[Music] pytubefix streams found: {len(streams)}")
        stream = streams.last()
        if not stream:
            print(f"[Music] pytubefix: no audio stream")
            return None
        print(f"[Music] pytubefix got stream: {yt.title} ({stream.abr})")
        return {
            "title":       yt.title,
            "url":         stream.url,
            "webpage_url": yt.watch_url,
            "duration":    yt.length or 0,
            "thumbnail":   yt.thumbnail_url or "",
            "uploader":    yt.author or "Unknown",
        }
    except Exception as e:
        print(f"[Music] pytubefix stream error: {type(e).__name__}: {e}")
        return None


def _ytdlp_fallback_sync(query: str) -> dict | None:
    """yt-dlp fallback for when pytubefix fails."""
    try:
        import yt_dlp
        _COOKIES_FILE = _ROOT / "cookies.txt"
        if not _COOKIES_FILE.exists():
            _alt = Path("/app/cookies.txt")
            if _alt.exists():
                _COOKIES_FILE = _alt
        opts = {
            "format":         "bestaudio/best",
            "noplaylist":     True,
            "quiet":          True,
            "no_warnings":    True,
            "default_search": "ytsearch",
            "source_address": "0.0.0.0",
            "extract_flat":   False,
        }
        if _COOKIES_FILE.exists():
            opts["cookiefile"] = str(_COOKIES_FILE)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if not info:
                return None
            if "entries" in info:
                info = info["entries"][0]
            print(f"[Music] yt-dlp fallback got: {info.get('title')}")
            return {
                "title":       info.get("title", "Unknown"),
                "url":         info.get("url") or info.get("webpage_url"),
                "webpage_url": info.get("webpage_url", ""),
                "duration":    info.get("duration", 0),
                "thumbnail":   info.get("thumbnail", ""),
                "uploader":    info.get("uploader", "Unknown"),
            }
    except Exception as e:
        print(f"[Music] yt-dlp fallback error: {e}")
        return None


# ── Public API ────────────────────────────────────────────────────

async def fetch_track(query: str) -> dict | None:
    """
    Fetch a track by name or URL.
    Tries pytubefix first, falls back to yt-dlp.
    """
    loop = asyncio.get_event_loop()

    # If it's a URL, go straight to stream
    if query.startswith("http"):
        result = await loop.run_in_executor(None, _pytube_stream_sync, query)
        if result:
            return result
        return await loop.run_in_executor(None, _ytdlp_fallback_sync, query)

    # Search query — find first result then get stream
    results = await loop.run_in_executor(None, _pytube_search_sync, query, 1)
    if results:
        result = await loop.run_in_executor(None, _pytube_stream_sync, results[0]["webpage_url"])
        if result:
            return result

    # Full fallback
    return await loop.run_in_executor(None, _ytdlp_fallback_sync, query)


async def search_tracks(query: str, limit: int = 5) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _pytube_search_sync, query, limit)


def format_duration(seconds: int) -> str:
    if not seconds:
        return "Live"
    h, rem = divmod(int(seconds), 3600)
    m, s   = divmod(rem, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"
