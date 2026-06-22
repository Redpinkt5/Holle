"""Bilibili audio search and download using yt-dlp."""

from __future__ import annotations

import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
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
        self._download_procs: dict[str, subprocess.Popen] = {}

    def resolve_url(self, url_or_bvid: str) -> Song | None:
        """Resolve a Bilibili URL or BV ID directly to a Song (no search needed).

        Accepts:
        - Full URL: https://www.bilibili.com/video/BV1gx411G7DN
        - Short URL: https://b23.tv/xxxxx
        - BV ID: BV1gx411G7DN
        """
        if not url_or_bvid:
            return None
        bvid = _extract_bvid(url_or_bvid)
        if not bvid:
            return None
        url = f"https://www.bilibili.com/video/{bvid}"
        return self._song_from_url(url)

    def search(self, query: str, max_results: int = 10) -> list[Song]:
        """Search Bilibili and return Song objects.

        Uses Bilibili API (via curl) for both search and metadata,
        avoiding yt-dlp which may be blocked by HTTP 412.
        Falls back to ddgs if Bilibili API returns nothing.
        """
        self._cancel_event.clear()

        songs = self._search_songs_from_api(query, max_results)
        if songs:
            return songs

        # Fallback to ddgs
        try:
            songs = self._search_urls_ddgs(query, max_results)
        except RuntimeError:
            return []
        return songs


    def _search_urls(self, query: str, max_results: int) -> list[str]:
        """Search Bilibili via official API (fast, comprehensive).

        Falls back to DuckDuckGo only if Bilibili API fails.
        """
        # Try Bilibili official API first — it has complete coverage
        urls = self._search_urls_bilibili(query, max_results)
        if urls:
            return urls

        # Fallback to DuckDuckGo if Bilibili API is unavailable
        if DDGS is None:
            raise RuntimeError("搜索失败: 无法连接 Bilibili，且 ddgs 也未安装")

        def _do_search() -> list[dict]:
            with DDGS() as ddgs:
                return list(
                    ddgs.text(f"{query} site:bilibili.com/video", max_results=max_results * 2)
                )

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_do_search)
                entries = future.result(timeout=10)
        except FuturesTimeoutError:
            raise RuntimeError("搜索超时，请检查网络或稍后重试") from None
        except Exception as exc:
            if self._cancel_event.is_set():
                return []
            raise RuntimeError(f"搜索失败: {exc}") from exc

        results: list[str] = []
        for r in entries:
            href = r.get("href", "")
            if _extract_bvid(href):
                results.append(href)
            if len(results) >= max_results:
                break
        return results

    def _search_songs_from_api(self, query: str, max_results: int) -> list[Song]:
        """Search Bilibili API and return Song objects with metadata from the API.

        Uses curl (shell=True to inherit WinINET proxy). Does NOT use yt-dlp for search,
        so it works even when yt-dlp is blocked by HTTP 412.
        """
        import json, subprocess

        encoded_query = quote(query, safe="")
        url = (
            f"https://api.bilibili.com/x/web-interface/search/type"
            f"?search_type=video&keyword={encoded_query}&page=1&pagesize={max_results}"
        )
        cmd = (
            f'curl -s -m 12 '
            f'-H "User-Agent: Mozilla/5.0" '
            f'-H "Referer: https://www.bilibili.com/" '
            f'"{url}"'
        )
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
            )
            if result.returncode != 0 or not result.stdout:
                return []
            data = json.loads(result.stdout)
        except Exception:
            return []

        if data.get("code") != 0:
            return []

        songs: list[Song] = []
        for item in (data.get("data", {}).get("result") or []):
            bvid = item.get("bvid", "")
            if not bvid:
                continue
            title = (item.get("title") or "").strip()
            if not title:
                continue
            # Clean HTML tag from title (Bilibili returns <em class="keyword">)
            import re as _re
            title = _re.sub(r"<[^>]+>", "", title)
            author = item.get("author", "未知UP主") or "未知UP主"
            duration_secs = item.get("duration", 0)
            # Duration format may be "3:45" or seconds
            if isinstance(duration_secs, str):
                parts = duration_secs.split(":")
                try:
                    if len(parts) == 2:
                        duration_secs = int(parts[0]) * 60 + int(parts[1])
                    elif len(parts) == 3:
                        duration_secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    else:
                        duration_secs = 0
                except Exception:
                    duration_secs = 0
            else:
                duration_secs = int(duration_secs) if duration_secs else 0
            arcurl = item.get("arcurl", "") or ""
            web_url = f"https://www.bilibili.com/video/{bvid}"
            song = Song(
                path=Path(""),
                title=f"{title} (web)",
                artist=author,
                duration=float(duration_secs),
                source="bilibili",
                bvid=bvid,
                web_url=web_url,
                cover_url="",
            )
            songs.append(song)
            if len(songs) >= max_results:
                break
        return songs

    def _song_from_url(self, url: str) -> Song | None:
        """Resolve a single Bilibili URL to Song using curl + search API.

        Does NOT use yt-dlp (yt-dlp is blocked by HTTP 412 in some networks).
        Returns None if the URL is invalid or the network call fails.
        """
        bvid = _extract_bvid(url)
        if not bvid:
            return None
        # Use _search_songs_from_api but pass bvid as the query
        # so it finds this exact video.
        songs = self._search_songs_from_api(bvid, max_results=1)
        for song in songs:
            if song.bvid == bvid:
                return song
        return None



    def download_audio(self, song: Song) -> Path:
        """Download audio for a Song into cache and return local path."""
        if not song.bvid:
            raise ValueError("Song 缺少 bvid")

        cached = audio_path(song.bvid)
        if cached:
            touch(song.bvid)
            return cached

        self._notify(f"正在下载: {song.title}")

        try:
            import yt_dlp
        except ImportError as exc:
            raise RuntimeError("yt-dlp 未安装") from exc

        cache_dir()
        out_path = str(CACHE_DIR / f"{song.bvid}_0.m4a")
        part_path = out_path + ".part"

        url = song.web_url or f"https://www.bilibili.com/video/{song.bvid}"
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--format", "bestaudio[ext=m4a]/bestaudio/best",
            "--output", part_path,
            "--quiet", "--no-warnings", "--no-progress",
            url,
        ]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self._download_procs[song.bvid] = proc

        try:
            stdout, stderr = proc.communicate()
            if self._cancel_event.is_set():
                raise RuntimeError("下载已取消")
            if proc.returncode != 0:
                raise RuntimeError(f"下载失败: {stderr.decode() or 'yt-dlp exited non-zero'}")
        finally:
            self._download_procs.pop(song.bvid, None)

        # Rename .part to final
        import os
        if os.path.exists(part_path):
            os.rename(part_path, out_path)
        elif not os.path.exists(out_path):
            # yt-dlp might output with different extension
            for p in CACHE_DIR.glob(f"{song.bvid}_0.*"):
                if p.suffix not in (".json", ".part"):
                    out_path = str(p)
                    break

        cached = audio_path(song.bvid)
        if not cached:
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
        for proc in list(self._download_procs.values()):
            proc.kill()
        self._download_procs.clear()

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