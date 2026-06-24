"""Bilibili audio search and download using yt-dlp."""

from __future__ import annotations

import json
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


def _ensure_ffmpeg() -> str:
    """Return path to ffmpeg executable, auto-installing imageio-ffmpeg if needed."""
    import shutil

    exe = shutil.which("ffmpeg")
    if exe:
        return exe

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "imageio-ffmpeg", "-q"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()


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
            songs = self._search_urls(query, max_results)
        except RuntimeError:
            return []
        return songs


    def _search_urls(self, query: str, max_results: int) -> list[Song]:
        """Search Bilibili URLs via DDGS and resolve each to Song objects.

        This is the fallback path when Bilibili API is unavailable.
        Returns Song objects (not URL strings) so it plugs directly into
        the search() return type.
        """
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

        songs: list[Song] = []
        for r in entries:
            href = r.get("href", "")
            if not _extract_bvid(href):
                continue
            song = self._song_from_url(href)
            if song:
                songs.append(song)
            if len(songs) >= max_results:
                break
        return songs

    def _search_songs_from_api(self, query: str, max_results: int) -> list[Song]:
        """Search Bilibili API and return Song objects with metadata from the API.

        Uses curl (shell=True to inherit WinINET proxy). Does NOT use yt-dlp for search,
        so it works even when yt-dlp is blocked by HTTP 412.

        Tries the newer ``search/all`` endpoint first (less likely to return a
        validation page), then falls back to ``search/type``.
        """

        def _try_endpoint(api_url: str) -> list[dict]:
            cmd = (
                f'curl -s -m 12 '
                f'-H "User-Agent: Mozilla/5.0" '
                f'-H "Referer: https://www.bilibili.com/" '
                f'"{api_url}"'
            )
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
            try:
                data = json.loads(result.stdout)
            except Exception:
                return []
            if data.get("code") != 0:
                return []
            return data.get("data", {}).get("result", {}).get("video", []) or []

        encoded_query = quote(query, safe="")

        # Primary: search/all (composite search) — returns JSON more reliably
        url_all = (
            f"https://api.bilibili.com/x/web-interface/search/all"
            f"?keyword={encoded_query}"
        )
        video_results = _try_endpoint(url_all)

        # Fallback: search/type (original dedicated video search)
        if not video_results:
            url_type = (
                f"https://api.bilibili.com/x/web-interface/search/type"
                f"?search_type=video&keyword={encoded_query}&page=1&pagesize={max_results}"
            )
            results = _try_endpoint(url_type)
            if results and isinstance(results, list):
                video_results = results

        songs: list[Song] = []
        for item in video_results:
            bvid = item.get("bvid", "")
            if not bvid:
                continue
            title = (item.get("title") or "").strip()
            if not title:
                continue
            # Clean HTML tag from title (Bilibili returns <em class="keyword">)
            title = re.sub(r"<[^>]+>", "", title)
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



    def get_audio_url(self, song: Song) -> str:
        """Resolve a Bilibili video to its audio stream URL (no download).

        Returns the audio URL if available, otherwise raises RuntimeError.
        """
        if not song.bvid:
            raise ValueError("Song 缺少 bvid")

        bvid = song.bvid
        headers = (
            '-H "User-Agent: Mozilla/5.0" '
            '-H "Referer: https://www.bilibili.com/" '
            '-H "Origin: https://www.bilibili.com"'
        )

        def _curl_get_json(api_url: str, timeout: int = 20) -> dict:
            cmd = f'curl -s -m {timeout - 3} {headers} "{api_url}"'
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            if result.returncode != 0 or not result.stdout:
                raise RuntimeError("网络或接口错误")
            try:
                return json.loads(result.stdout)
            except Exception as exc:
                raise RuntimeError(f"JSON解析错误 ({exc})") from exc

        # Get cid from video page API
        page_api = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        page_info = _curl_get_json(page_api, timeout=20)
        if page_info.get("code") != 0:
            raise RuntimeError(
                f"获取视频信息失败：B站返回 {page_info.get('message', page_info.get('code'))}"
            )

        cid = page_info.get("data", {}).get("cid", "")
        if not cid:
            raise RuntimeError("获取视频信息失败：缺少 cid")

        # Get the audio URL from Bilibili playurl API
        playurl_api = (
            f"https://api.bilibili.com/x/player/playurl"
            f"?bvid={bvid}&cid={cid}&qn=80&fnval=0&fnver=0&otype=json"
        )
        playinfo = _curl_get_json(playurl_api, timeout=20)
        if playinfo.get("code") != 0:
            raise RuntimeError(
                f"获取音频地址失败：B站返回 {playinfo.get('message', playinfo.get('code'))}"
            )

        durl_list = playinfo.get("data", {}).get("durl", [{}])
        if not durl_list:
            raise RuntimeError("获取音频地址失败：未找到音频流")

        audio_url = durl_list[0].get("url", "")
        if not audio_url:
            raise RuntimeError("获取音频地址失败：音频URL为空")
        return audio_url

    def download_audio(self, song: Song) -> Path:
        """Download audio for a Song into cache and return local path.

        Uses curl (not yt-dlp) to avoid HTTP 412 blocking.
        """
        if not song.bvid:
            raise ValueError("Song 缺少 bvid")

        cached = audio_path(song.bvid)
        if cached:
            touch(song.bvid)
            return cached

        self._notify(f"正在缓冲: {song.title}")

        bvid = song.bvid
        audio_url = self.get_audio_url(song)
        headers = (
            '-H "User-Agent: Mozilla/5.0" '
            '-H "Referer: https://www.bilibili.com/" '
            '-H "Origin: https://www.bilibili.com"'
        )

        cache_dir()
        out_path = str(CACHE_DIR / f"{bvid}_0.m4a")
        part_path = out_path + ".part"

        cmd_download = (
            f'curl -s -m 300 {headers} '
            f'-o "{part_path}" '
            f'"{audio_url}"'
        )
        proc = subprocess.Popen(
            cmd_download,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._download_procs[bvid] = proc

        try:
            _, stderr_bytes = proc.communicate(timeout=330)
            if self._cancel_event.is_set():
                raise RuntimeError("缓冲已取消")
            if proc.returncode != 0:
                stderr_text = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
                raise RuntimeError(f"缓冲失败: {stderr_text or f'curl exited {proc.returncode}'}")
        finally:
            self._download_procs.pop(bvid, None)

        # Rename .part to final
        import os
        if os.path.exists(part_path):
            os.rename(part_path, out_path)

        # Convert m4a to mp3 so pygame can play it
        final_path = Path(out_path)
        if final_path.suffix.lower() == ".m4a":
            mp3_path = final_path.with_suffix(".mp3")
            try:
                ffmpeg = _ensure_ffmpeg()
                self._notify(f"正在转码: {song.title}")
                cmd_convert = [
                    ffmpeg,
                    "-y",
                    "-i", str(final_path),
                    "-vn",
                    "-ar", "44100",
                    "-ac", "2",
                    "-b:a", "192k",
                    str(mp3_path),
                ]
                subprocess.run(cmd_convert, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
                if mp3_path.exists():
                    try:
                        final_path.unlink()
                    except Exception:
                        pass
                    out_path = str(mp3_path)
            except Exception as exc:
                # If conversion fails, keep the original m4a and let the caller decide
                self._notify(f"转码失败，使用原始音频: {exc}")

        cached = audio_path(bvid)
        if not cached:
            raise RuntimeError("缓冲后未找到音频文件")

        save_metadata(
            bvid,
            {
                "title": song.title,
                "artist": song.artist,
                "duration": song.duration,
                "web_url": song.web_url,
                "cover_url": song.cover_url,
            },
        )
        cleanup_from_settings()
        self._notify(f"{song.title} 缓冲完成")
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