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

    def _search_urls_bilibili(self, query: str, max_results: int) -> list[str]:
        """Search Bilibili official API using curl (works in restricted networks).

        urllib cannot reach api.bilibili.com from some environments, but curl can.
        Uses shell=True so curl inherits the system proxy from Windows.
        Falls back to empty list if curl fails.
        """
        import json, subprocess

        encoded_query = quote(query, safe="")
        url = (
            f"https://api.bilibili.com/x/web-interface/search/type"
            f"?search_type=video&keyword={encoded_query}&page=1&pagesize={max_results}"
        )
        cmd = (
            f'curl -s -m 10 '
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

        results: list[str] = []
        for item in (data.get("data", {}).get("result") or []):
            bvid = item.get("bvid", "")
            if bvid:
                results.append(f"https://www.bilibili.com/video/{bvid}")
            if len(results) >= max_results:
                break
        return results

    def _song_from_url(self, url: str) -> Song | None:
        """Use yt-dlp to fetch metadata for a Bilibili URL.

        Returns None if video does not exist.
        Raises RuntimeError if network is blocked (412/403) or yt-dlp is missing.
        """
        try:
            import yt_dlp
        except ImportError as exc:
            raise RuntimeError("yt-dlp 未安装") from exc

        bvid = _extract_bvid(url)
        if not bvid:
            return None

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 10,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except Exception as exc:
                err_text = str(exc).lower()
                # 412 / 403 = B站拒绝访问（IP受限或需登录）
                if any(kw in err_text for kw in ("412", "403", "precondition failed",
                                                  "http error 412", "http error 403",
                                                  "precondition failed", "access denied")):
                    raise RuntimeError(
                        "B站无法访问（HTTP 412/403），可能是网络受限或需要登录。"
                        "请尝试：1. 在浏览器中打开此链接确认可访问；2. 将视频页面截图发给我"
                    ) from exc
                # 其他错误（视频不存在、已删除等）→ 返回 None
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
