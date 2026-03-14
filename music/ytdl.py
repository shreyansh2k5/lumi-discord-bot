# music/ytdl.py
# Uses Invidious API to get YouTube stream URLs — no signature solving needed.
# Falls back to next instance if one is down.

import asyncio
import os
import re
import shutil
from pathlib import Path
import aiohttp

# ── FFmpeg path ───────────────────────────────────────────────────
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

# ── Invidious instances (tried in order, first working one is used) ──
INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net",
    "https://invidious.privacyredirect.com",
    "https://invidious.nerdvpn.de",
    "https://yt.cdaut.de",
    "https://invidious.io.lol",
]


def _extract_video_id(url: str) -> str | None:
    """Extracts YouTube video ID from a URL, or returns None if not a URL."""
    patterns = [
        r"(?:v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})",
        r"music\.youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


async def _search_invidious(query: str, limit: int = 5) -> list[dict]:
    """Search YouTube via Invidious API."""
    async with aiohttp.ClientSession() as session:
        for instance in INVIDIOUS_INSTANCES:
            try:
                url = f"{instance}/api/v1/search"
                params = {"q": query, "type": "video", "fields": "title,videoId,lengthSeconds,author,videoThumbnails"}
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = []
                        for item in data[:limit]:
                            thumb = ""
                            thumbs = item.get("videoThumbnails", [])
                            if thumbs:
                                thumb = thumbs[-1].get("url", "")
                            results.append({
                                "title":       item.get("title", "Unknown"),
                                "webpage_url": f"https://www.youtube.com/watch?v={item['videoId']}",
                                "video_id":    item["videoId"],
                                "duration":    item.get("lengthSeconds", 0),
                                "uploader":    item.get("author", "Unknown"),
                                "thumbnail":   thumb,
                            })
                        return results
            except Exception as e:
                print(f"[Music] Invidious search failed on {instance}: {e}")
                continue
    return []


async def _get_stream_url(video_id: str) -> dict | None:
    """Gets direct audio stream URL from Invidious for a video ID."""
    async with aiohttp.ClientSession() as session:
        for instance in INVIDIOUS_INSTANCES:
            try:
                url = f"{instance}/api/v1/videos/{video_id}"
                params = {"fields": "title,lengthSeconds,author,videoThumbnails,adaptiveFormats,formatStreams"}
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()

                    # Try adaptiveFormats first (audio-only streams)
                    best_audio = None
                    best_bitrate = 0
                    for fmt in data.get("adaptiveFormats", []):
                        if fmt.get("type", "").startswith("audio/"):
                            bitrate = fmt.get("bitrate", 0)
                            if bitrate > best_bitrate:
                                best_bitrate = bitrate
                                best_audio = fmt.get("url")

                    # Fall back to formatStreams (video+audio combined)
                    if not best_audio:
                        streams = data.get("formatStreams", [])
                        if streams:
                            best_audio = streams[0].get("url")

                    if not best_audio:
                        continue

                    thumb = ""
                    thumbs = data.get("videoThumbnails", [])
                    if thumbs:
                        thumb = thumbs[0].get("url", "")

                    return {
                        "title":       data.get("title", "Unknown"),
                        "url":         best_audio,
                        "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
                        "duration":    data.get("lengthSeconds", 0),
                        "thumbnail":   thumb,
                        "uploader":    data.get("author", "Unknown"),
                    }
            except Exception as e:
                print(f"[Music] Invidious stream failed on {instance}: {e}")
                continue
    return None


async def fetch_track(query: str) -> dict | None:
    """
    Main entry point. Accepts a YouTube URL or search text.
    Returns a track dict with a direct stream URL.
    """
    # If it's a YouTube URL, extract the video ID directly
    video_id = _extract_video_id(query)

    if not video_id:
        # It's a search query — find the first result
        results = await _search_invidious(query, limit=1)
        if not results:
            return None
        video_id = results[0]["video_id"]

    return await _get_stream_url(video_id)


def format_duration(seconds: int) -> str:
    if not seconds:
        return "Live"
    h, rem = divmod(int(seconds), 3600)
    m, s   = divmod(rem, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


async def search_tracks(query: str, limit: int = 5) -> list[dict]:
    """Returns up to `limit` search results for the dropdown."""
    return await _search_invidious(query, limit)
