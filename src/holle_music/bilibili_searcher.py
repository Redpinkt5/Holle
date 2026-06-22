"""Bilibili audio search and download using yt-dlp."""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, unquote, urlparse

from holle_music.models import Song
from holle_music.online_cache import (
    CACHE_DIR,
    audio_path,
    cache_dir,
    cleanup_from_settings,
    is_cached,
    save_metadata,
    touch,
)


# BV 号正则：以 BV 开头，后跟 10 个字母/数字
_BVID_RE = re.compile(r"BV[0-9A-Za-z]{10}")

# ddgs for DuckDuckGo search
try:
    from ddgs import DDGS  # noqa: F401
except ImportError:
    DDGS = None

# yt_dlp for metadata extraction and download
try:
    import yt_dlp  # noqa: F401
except ImportError:
    yt_dlp = None


def _extract_bvid(url: str) -> str | None:
    """Extract bvid from a Bilibili video URL."""
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    # Accept bilibili.com, www.bilibili.com, and b23.tv short URLs
    if not any(h in netloc for h in ("bilibili.com", "b23.tv")):
        return None
    # Search in the unquoted path
    m = _BVID_RE.search(unquote(parsed.path))
    return m.group(0) if m else None


class BilibiliSearcher:
    """Search Bilibili videos and download their audio streams."""

    def __init__(self, progress_callback: Callable[[str], None] | None = None) -> None:
        self._progress_callback = progress_callback
        self._cancel_event = threading.Event()

    def search(self, query: str, max_results: int = 10) -> list[Song]:
        """Search Bilibili and return Song objects."""
        self._cancel_event.clear()

        urls = self._search_urls(query, max_results)
        songs: list[Song] = []
        for url in urls:
            if self._cancel_event.is_set():
                break
            song = self._song_from_url(url)
            if song:
                songs.append(song)
        return songs

    def _search_urls(self, query: str, max_results: int) -> list[str]:
        """Use DuckDuckGo to find Bilibili video URLs."""
        if DDGS is None:
            raise RuntimeError("ddgs 未安装")

        try:
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(f"{query} site:bilibili.com/video", max_results=max_results * 2):
                    href = r.get("href", "")
                    if _extract_bvid(href):
                        results.append(href)
                    if len(results) >= max_results:
                        break
            return results
        except Exception as exc:
            if self._cancel_event.is_set():
                return []
            raise RuntimeError(f"搜索失败: {exc}") from exc

    def _song_from_url(self, url: str) -> Song | None:
        """Use yt-dlp to fetch metadata for a Bilibili URL."""
        if yt_dlp is None:
            return None

        bvid = _extract_bvid(url)
        if not bvid:
            return None

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except Exception:
                return None

            if not info:
                return None

            title = (info.get("title") or "").strip()
            uploader = info.get("uploader") or "未知UP主"
            duration = info.get("duration") or 0.0
            thumbnails = info.get("thumbnails") or []
            cover_url = thumbnails[-1].get("url", "") if thumbnails else ""

            if not title:
                return None

            return Song(
                path=Path(""),
                title=f"{title} (web)",
                artist=uploader,
                duration=float(duration) if duration else 0.0,
                source="bilibili",
                bvid=bvid,
                web_url=url,
                cover_url=cover_url,
            )

    def download_audio(self, song: Song) -> Path:
        """Download audio for a Song into cache and return local path."""
        if not song.bvid:
            raise ValueError("Song 缺少 bvid")

        cached = audio_path(song.bvid)
        if cached:
            touch(song.bvid)
            return cached

        self._notify(f"正在下载: {song.title}")
        if yt_dlp is None:
            raise RuntimeError("yt-dlp 未安装")

        cache_dir()
        outtmpl = str(CACHE_DIR / f"{song.bvid}_0.%(ext)s")
        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                url = song.web_url or f"https://www.bilibili.com/video/{song.bvid}"
                ydl.download([url])
            except Exception as exc:
                if self._cancel_event.is_set():
                    raise RuntimeError("下载已取消") from exc
                raise RuntimeError(f"下载失败: {exc}") from exc

        cached = audio_path(song.bvid)
        if not cached:
            candidates = [
                p for p in CACHE_DIR.glob(f"{song.bvid}_0.*")
                if p.suffix not in (".json", ".part")
            ]
            if candidates:
                cached = candidates[0]
            else:
                raise RuntimeError("下载后未找到音频文件")

        save_metadata(
            song.bvid,
            {
                "title": song.title,
                "artist": song.artist,
                "duration": song.duration,
                "web_url": song.web_url,
                "cover_url": song.cover_url,
            },
        )
        cleanup_from_settings()
        self._notify(f"{song.title} 下载完成")
        return cached

    def cancel(self) -> None:
        """Signal in-flight search/download to stop."""
        self._cancel_event.set()

    def _notify(self, msg: str) -> None:
        if self._progress_callback:
            try:
                self._progress_callback(msg)
            except Exception:
                pass


def is_network_error(exc: Exception) -> bool:
    """Return True if exception looks like a network failure."""
    text = str(exc).lower()
    return any(kw in text for kw in ("network", "connection", "timeout", "errno", "unreachable", "dns"))
