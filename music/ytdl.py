# music/ytdl.py
# Uses Invidious public API to get YouTube stream URLs.
# No yt-dlp signature solving, no cookies, no JS needed.

import asyncio
import os
import re
import shutil
from pathlib import Path
import aiohttp

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

# ── Invidious instances ───────────────────────────────────────────
INSTANCES = [
    "https://inv.nadeko.net",
    "https://invidious.privacyredirect.com",
    "https://invidious.nerdvpn.de",
    "https://yt.cdaut.de",
    "https://invidious.io.lol",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; LumiBot/1.0)"}


def _video_id(url: str) -> str | None:
    for pat in [
        r"(?:v=|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})",
        r"music\.youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})",
    ]:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


async def _get_session() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(headers=HEADERS)


async def _search(query: str, limit: int = 5) -> list[dict]:
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        for inst in INSTANCES:
            try:
                async with session.get(
                    f"{inst}/api/v1/search",
                    params={"q": query, "type": "video"},
                    timeout=aiohttp.ClientTimeout(total=8)
                ) as r:
                    if r.status != 200:
                        continue
                    items = await r.json()
                    results = []
                    for item in items[:limit]:
                        thumbs = item.get("videoThumbnails", [])
                        results.append({
                            "title":       item.get("title", "Unknown"),
                            "webpage_url": f"https://www.youtube.com/watch?v={item['videoId']}",
                            "video_id":    item["videoId"],
                            "duration":    item.get("lengthSeconds", 0),
                            "uploader":    item.get("author", "Unknown"),
                            "thumbnail":   thumbs[0]["url"] if thumbs else "",
                        })
                    print(f"[Music] Search via {inst}: {len(results)} results")
                    return results
            except Exception as e:
                print(f"[Music] Search failed {inst}: {e}")
    print("[Music] All Invidious instances failed for search")
    return []


async def _stream(video_id: str) -> dict | None:
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        for inst in INSTANCES:
            try:
                async with session.get(
                    f"{inst}/api/v1/videos/{video_id}",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as r:
                    if r.status != 200:
                        print(f"[Music] {inst} returned {r.status} for {video_id}")
                        continue
                    data = await r.json()

                    # Best audio-only stream
                    best_url, best_br = None, 0
                    for fmt in data.get("adaptiveFormats", []):
                        if "audio" in fmt.get("type", ""):
                            br = int(fmt.get("bitrate", 0))
                            if br > best_br:
                                best_br = br
                                best_url = fmt.get("url")

                    # Fallback to combined stream
                    if not best_url:
                        streams = data.get("formatStreams", [])
                        if streams:
                            best_url = streams[0].get("url")

                    if not best_url:
                        print(f"[Music] No playable URL from {inst} for {video_id}")
                        continue

                    thumbs = data.get("videoThumbnails", [])
                    print(f"[Music] Got stream from {inst} for {video_id}")
                    return {
                        "title":       data.get("title", "Unknown"),
                        "url":         best_url,
                        "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
                        "duration":    data.get("lengthSeconds", 0),
                        "thumbnail":   thumbs[0]["url"] if thumbs else "",
                        "uploader":    data.get("author", "Unknown"),
                    }
            except Exception as e:
                print(f"[Music] Stream failed {inst}: {e}")
    print(f"[Music] All instances failed for video {video_id}")
    return None


async def fetch_track(query: str) -> dict | None:
    vid = _video_id(query)
    if not vid:
        results = await _search(query, limit=1)
        if not results:
            return None
        vid = results[0]["video_id"]
    return await _stream(vid)


async def search_tracks(query: str, limit: int = 5) -> list[dict]:
    return await _search(query, limit)


def format_duration(seconds: int) -> str:
    if not seconds:
        return "Live"
    h, rem = divmod(int(seconds), 3600)
    m, s   = divmod(rem, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"
