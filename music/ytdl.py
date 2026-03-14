# music/ytdl.py
# Primary: pytubefix with WEB_EMBED client (most stable, no JS challenge)
# Fallback: yt-dlp with cookies

import asyncio
import os
import shutil
from pathlib import Path

_ROOT = Path(__file__).parent.parent.resolve()

# ── FFmpeg ────────────────────────────────────────────────────────
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
# Try multiple clients in order until one works
_PYTUBE_CLIENTS = ["WEB_EMBED", "TV_EMBED", "WEB", "MWEB"]

def _pytube_stream_sync(url: str) -> dict | None:
    try:
        from pytubefix import YouTube
        for client in _PYTUBE_CLIENTS:
            try:
                yt = YouTube(url, client=client)
                stream = yt.streams.filter(only_audio=True).order_by("abr").last()
                if not stream:
                    stream = yt.streams.first()
                if stream and stream.url:
                    print(f"[Music] ✅ pytubefix [{client}]: {yt.title}")
                    return {
                        "title":       yt.title,
                        "url":         stream.url,
                        "webpage_url": yt.watch_url,
                        "duration":    yt.length or 0,
                        "thumbnail":   yt.thumbnail_url or "",
                        "uploader":    yt.author or "Unknown",
                    }
            except Exception as e:
                print(f"[Music] pytubefix [{client}] failed: {type(e).__name__}: {e}")
                continue
        return None
    except Exception as e:
        print(f"[Music] pytubefix import error: {e}")
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
        print(f"[Music] pytubefix search: {len(results)} results")
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
            print(f"[Music] yt-dlp: {info.get('title')}")
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
    loop = asyncio.get_event_loop()

    if query.startswith("http"):
        result = await loop.run_in_executor(None, _pytube_stream_sync, query)
        if result:
            return result
        return await loop.run_in_executor(None, _ytdlp_sync, query)

    results = await loop.run_in_executor(None, _pytube_search_sync, query, 1)
    if results:
        result = await loop.run_in_executor(None, _pytube_stream_sync, results[0]["webpage_url"])
        if result:
            return result

    return await loop.run_in_executor(None, _ytdlp_sync, query)


async def search_tracks(query: str, limit: int = 5) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _pytube_search_sync, query, limit)


def format_duration(seconds: int) -> str:
    if not seconds:
        return "Live"
    h, rem = divmod(int(seconds), 3600)
    m, s   = divmod(rem, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"
