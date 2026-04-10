# music/engine.py
# All audio engine logic: FFmpeg discovery, yt-dlp extraction, queue model.
# cogs/music.py imports from here and contains only Discord commands.

import asyncio
import shutil
import os
import discord
import yt_dlp

yt_dlp.utils.bug_reports_message = lambda: ''


# ───────────── FFmpeg discovery ─────────────────────────────────────────────

def _find_ffmpeg() -> str:
    """
    Locate the FFmpeg binary robustly so PM2's stripped PATH never causes a
    'ffmpeg was not found' error at runtime.
    Priority: PATH → /usr/bin/ffmpeg (Ubuntu) → ./ffmpeg.exe (Windows dev).
    """
    found = shutil.which("ffmpeg")
    if found:
        return found
    if os.path.isfile("/usr/bin/ffmpeg"):
        return "/usr/bin/ffmpeg"
    local = os.path.join(os.path.dirname(__file__), "..", "ffmpeg.exe")
    if os.path.isfile(local):
        return os.path.abspath(local)
    return "ffmpeg"  # last resort — will raise FileNotFoundError clearly


FFMPEG_PATH = _find_ffmpeg()
print(f"[Music] FFmpeg resolved to: {FFMPEG_PATH}")

FFMPEG_OPTS: dict = {
    "executable":     FFMPEG_PATH,
    # Reconnect flags keep HTTP streams alive through brief CDN hiccups
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options":        "-vn -loglevel error",
}


# ───────────── yt-dlp instances ─────────────────────────────────────────────
#
# Two separate instances with different purposes:
#
# ytdl_meta   — flat / fast. Used ONLY for the "Added to queue" preview.
#               Returns title + duration but NO stream URL.
#
# ytdl_stream — full extraction. Called RIGHT BEFORE playback starts so the
#               CDN URL is always fresh (SoundCloud/YouTube URLs expire in
#               minutes; pre-fetching causes silent 403s → premature skips).

YTDL_META_OPTS: dict = {
    "format":         "bestaudio/best",
    "noplaylist":     True,
    "quiet":          True,
    "no_warnings":    True,
    "default_search": "scsearch",   # SoundCloud – bypasses Azure YouTube blocks
    "source_address": "0.0.0.0",
    "extract_flat":   "in_playlist",  # skip stream URL resolution entirely
}

YTDL_STREAM_OPTS: dict = {
    "format":         "bestaudio/best",
    "noplaylist":     True,
    "quiet":          True,
    "no_warnings":    True,
    "default_search": "scsearch",
    "source_address": "0.0.0.0",
    # Try less-restricted clients first to reduce 403s on YouTube
    "extractor_args": {
        "youtube": {"player_client": ["tv_embedded", "ios", "web"]}
    },
}

ytdl_meta   = yt_dlp.YoutubeDL(YTDL_META_OPTS)
ytdl_stream = yt_dlp.YoutubeDL(YTDL_STREAM_OPTS)


# ───────────── Helpers ───────────────────────────────────────────────────────

def fmt_time(seconds: int) -> str:
    """Format seconds as M:SS (or 'Live' for streams)."""
    if not seconds:
        return "Live"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02}"


# ───────────── Async extraction ──────────────────────────────────────────────

async def fetch_meta(query: str, loop: asyncio.AbstractEventLoop) -> dict:
    """
    Fast metadata-only fetch — no stream URL extracted.
    Returns a track dict safe to store in the queue.

    Track dict shape:
        title, duration, webpage_url, thumbnail, query, requester (empty)
    """
    def _run() -> dict:
        info = ytdl_meta.extract_info(query, download=False)
        if info and "entries" in info:
            info = info["entries"][0]
        if not info:
            raise ValueError("No results found.")
        return {
            "title":       info.get("title",       "Unknown"),
            "duration":    info.get("duration",    0),
            "webpage_url": info.get("webpage_url") or info.get("url", ""),
            "thumbnail":   info.get("thumbnail",   ""),
            "query":       query,   # kept so we can re-resolve at play time
            "requester":   "",      # filled by the caller
        }

    return await loop.run_in_executor(None, _run)


async def create_source(
    track: dict,
    loop: asyncio.AbstractEventLoop,
) -> discord.PCMVolumeTransformer:
    """
    Fetch a BRAND-NEW stream URL and wrap it in a playable audio source.
    Always called immediately before vc.play(), never at queue time.

    Uses webpage_url if available (more precise), falling back to the
    original search query.
    """
    lookup = track.get("webpage_url") or track["query"]

    def _run() -> dict:
        info = ytdl_stream.extract_info(lookup, download=False)
        if info and "entries" in info:
            info = info["entries"][0]
        if not info or not info.get("url"):
            raise ValueError(f"Could not resolve stream for: {track['title']}")
        return info

    info = await loop.run_in_executor(None, _run)

    raw    = discord.FFmpegPCMAudio(info["url"], **FFMPEG_OPTS)
    player = discord.PCMVolumeTransformer(raw, volume=1.0)

    # Attach metadata so commands like $np and $queue stay accurate
    player.title     = info.get("title",       track["title"])
    player.duration  = info.get("duration",    track.get("duration", 0))
    player.webpage   = info.get("webpage_url", track.get("webpage_url", ""))
    player.thumbnail = info.get("thumbnail",   track.get("thumbnail", ""))
    player.requester = track.get("requester",  "Unknown")

    return player


# ───────────── Queue model ───────────────────────────────────────────────────

class GuildQueue:
    """
    Per-guild playback state.

    `queue`   — list of lightweight track dicts (no audio sources / stream URLs)
    `current` — dict of the track currently playing, or None
    """

    __slots__ = ("queue", "current")

    def __init__(self) -> None:
        self.queue:   list[dict]       = []
        self.current: dict | None      = None

    def clear(self) -> None:
        self.queue.clear()
        self.current = None


# ───────────── Search ────────────────────────────────────────────────────────

async def search_tracks(
    query: str,
    loop: asyncio.AbstractEventLoop,
    limit: int = 5,
) -> list[dict]:
    """
    Search SoundCloud for `limit` tracks and return lightweight metadata dicts.
    No stream URLs are extracted — they are fetched fresh when a track is played.
    """
    def _run() -> list[dict]:
        opts = {
            "quiet":          True,
            "no_warnings":    True,
            "extract_flat":   True,   # fast — no stream URL resolution
            "default_search": "scsearch",
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"scsearch{limit}:{query}", download=False)
            results: list[dict] = []
            for e in (info.get("entries") or [])[:limit]:
                # For scsearch flat extraction, `url` is the SoundCloud page URL
                page_url = e.get("url") or e.get("webpage_url", "")
                results.append({
                    "title":       e.get("title",    "Unknown"),
                    "duration":    e.get("duration", 0),
                    "webpage_url": page_url,
                    "thumbnail":   e.get("thumbnail", ""),
                    # query is the fallback used by create_source if webpage_url is empty
                    "query":       page_url or f"scsearch1:{e.get('title', query)}",
                    "requester":   "",
                })
            return results

    return await loop.run_in_executor(None, _run)
