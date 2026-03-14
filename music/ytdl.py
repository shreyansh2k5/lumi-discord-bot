# music/ytdl.py
# Primary: pytubefix with cookies
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


def _load_cookie_jar() -> MozillaCookieJar | None:
    if not _has_cookies:
        return None
    try:
        jar = MozillaCookieJar(str(_COOKIES_FILE))
        jar.load(ignore_discard=True, ignore_expires=True)
        print(f"[Music] Loaded {len(list(jar))} cookies")
        return jar
    except Exception as e:
        print(f"[Music] Cookie load error: {e}")
        return None


# ── pytubefix ────────────────────────────────────────────────────

def _pytube_stream_sync(url: str) -> dict | None:
    try:
        import requests
        from pytubefix import YouTube
        from pytubefix.innertube import InnerTube

        print(f"[Music] pytubefix fetching: {url}")

        # Inject cookies into pytubefix's requests session
        jar = _load_cookie_jar()
        if jar:
            # Patch the default session used by InnerTube
            session = requests.Session()
            session.cookies = jar
            InnerTube._default_clients  # just access to ensure loaded
            original_session = getattr(InnerTube, '_session', None)

        yt = YouTube(url, use_oauth=False, allow_oauth_cache=False)

        # Manually set cookies on the yt object's innertube client
        if jar and hasattr(yt, '_innertube_client'):
            yt._innertube_client.session.cookies = jar

        print(f"[Music] pytubefix title check...")
        title = yt.title
        print(f"[Music] pytubefix title: {title}")

        streams = yt.streams.filter(only_audio=True).order_by("abr")
        print(f"[Music] pytubefix audio streams: {len(streams)}")
        stream = streams.last()

        if not stream:
            print("[Music] pytubefix: no audio stream found")
            return None

        print(f"[Music] ✅ pytubefix success: {title} @ {stream.abr}")
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
        print(f"[Music] pytubefix searching: {query}")
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
        print(f"[Music] pytubefix search error: {type(e).__name__}: {e}")
        return []


# ── yt-dlp fallback ───────────────────────────────────────────────

def _ytdlp_sync(query: str) -> dict | None:
    try:
        import yt_dlp
        print(f"[Music] yt-dlp fallback: {query}")
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
            print(f"[Music] yt-dlp got: {info.get('title')}")
            return {
                "title":       info.get("title", "Unknown"),
                "url":         info.get("url") or info.get("webpage_url"),
                "webpage_url": info.get("webpage_url", ""),
                "duration":    info.get("duration", 0),
                "thumbnail":   info.get("thumbnail", ""),
                "uploader":    info.get("uploader", "Unknown"),
            }
    except Exception as e:
        print(f"[Music] yt-dlp error: {type(e).__name__}: {e}")
        return None


# ── Public API ────────────────────────────────────────────────────

async def fetch_track(query: str) -> dict | None:
    loop = asyncio.get_event_loop()

    if query.startswith("http"):
        # Direct URL — try pytubefix first
        result = await loop.run_in_executor(None, _pytube_stream_sync, query)
        if result:
            return result
    else:
        # Search — find first result then stream
        results = await loop.run_in_executor(None, _pytube_search_sync, query, 1)
        if results:
            result = await loop.run_in_executor(None, _pytube_stream_sync, results[0]["webpage_url"])
            if result:
                return result

    # yt-dlp fallback
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
