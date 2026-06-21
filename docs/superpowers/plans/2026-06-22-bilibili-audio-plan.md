# Bilibili 在线音频搜索与播放实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Holle Music v0.4.0-beta 实现 Bilibili 在线音频搜索、下载缓存与播放功能。

**Architecture:** 新增 `bilibili_searcher` 负责 B 站搜索/下载，`online_cache` 负责缓存/LRU；`Song` 模型扩展 online 字段；终端、Pet、AI 工具统一复用这两层；音频下载到本地缓存后由现有 `Player` 播放。

**Tech Stack:** Python 3.10+, textual, pygame, yt-dlp, pytest

---

## 文件结构

| 文件 | 类型 | 职责 |
|---|---|---|
| `src/holle_music/models.py` | 修改 | `Song` 增加 `source/bvid/web_url/cover_url` 字段。 |
| `src/holle_music/settings.py` | 修改 | 默认配置增加缓存上限。 |
| `src/holle_music/online_cache.py` | 新增 | 缓存目录、命中查询、LRU 清理、手动清理。 |
| `src/holle_music/bilibili_searcher.py` | 新增 | B 站搜索、音频下载、取消控制。 |
| `src/holle_music/app.py` | 修改 | `/search` 扩展、新增 `/cache` 命令、后台下载调度。 |
| `src/holle_music/tui_tools.py` | 修改 | 新增 `search_bilibili` 工具；`play_song` 支持 B 站。 |
| `src/holle_music/pet/commands.py` | 修改 | Pet `/search` 扩展。 |
| `src/holle_music/pet/ai_tools.py` | 修改 | Pet AI 工具扩展。 |
| `pyproject.toml` | 修改 | 新增 `yt-dlp` 依赖；版本改为 `0.4.0-beta`。 |
| `tests/test_online_cache.py` | 新增 | 缓存模块单元测试。 |
| `tests/test_bilibili_searcher.py` | 新增 | 搜索模块单元测试（mock yt-dlp）。 |
| `tests/test_models.py` | 新增/修改 | `Song` 序列化测试。 |
| `README.md` | 修改 | 功能说明。 |
| `memory/modules/` | 新增/修改 | 新模块记忆与索引更新。 |

---

## Task 1: 添加 yt-dlp 依赖并升级版本号

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 修改 `pyproject.toml`**

将版本改为 `0.4.0-beta`，并在 `dependencies` 末尾追加 `yt-dlp`：

```toml
[project]
name = "holle-music"
version = "0.4.0-beta"
...
dependencies = [
    "textual>=0.40.0",
    "pygame>=2.5.0",
    "mutagen>=1.47.0",
    "librosa>=0.10.0",
    "Pillow>=10.0.0",
    "openai>=1.0.0",
    "ddgs>=3.0.0",
    "yt-dlp>=2024.0.0",
    "pywin32>=306; platform_system=='Windows'",
]
```

- [ ] **Step 2: 本地安装依赖并验证**

Run:
```bash
cd E:/DDDESKKKK/holle_music
pip install -e .
python -c "import yt_dlp; print(yt_dlp.version.__version__)"
```
Expected: 输出版本号，无 ImportError。

- [ ] **Step 3: 提交**

```bash
git add pyproject.toml
git commit -m "chore: bump version to 0.4.0-beta and add yt-dlp dependency"
```

---

## Task 2: 扩展 Song 模型支持在线来源

**Files:**
- Modify: `src/holle_music/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: 编写序列化测试**

```python
# tests/test_models.py
from pathlib import Path
from holle_music.models import Song


def test_song_defaults_to_local():
    song = Song(path=Path("/music/song.mp3"), title="Test")
    assert song.source == "local"
    assert song.bvid == ""
    assert song.web_url == ""
    assert song.cover_url == ""


def test_song_online_fields():
    song = Song(
        path=Path(""),
        title="晴天 (web)",
        artist="周杰伦",
        source="bilibili",
        bvid="BV1xx411c7mD",
        web_url="https://www.bilibili.com/video/BV1xx411c7mD",
        cover_url="https://example.com/cover.jpg",
    )
    assert song.source == "bilibili"
    assert song.bvid == "BV1xx411c7mD"


def test_song_dict_roundtrip():
    song = Song(
        path=Path("/cache/BV1xx411c7mD_0.m4a"),
        title="晴天 (web)",
        artist="周杰伦",
        source="bilibili",
        bvid="BV1xx411c7mD",
    )
    data = song.__dict__.copy()
    data["path"] = str(data["path"])
    restored = Song(**{k: v for k, v in data.items()})
    assert restored.bvid == song.bvid
    assert restored.source == song.source
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
pytest tests/test_models.py -v
```
Expected: 因 `Song` 缺少字段而失败。

- [ ] **Step 3: 修改 `src/holle_music/models.py`**

```python
@dataclass(eq=False)
class Song:
    """一首歌曲."""

    path: Path
    title: str = ""
    artist: str = "未知艺术家"
    album: str = "未知专辑"
    duration: float = 0.0
    source: str = "local"          # "local" | "bilibili"
    bvid: str = ""                 # B 站视频 ID
    web_url: str = ""              # B 站视频页面 URL
    cover_url: str = ""            # 封面图 URL

    def __post_init__(self):
        if isinstance(self.path, str):
            self.path = Path(self.path)
        if not self.title:
            self.title = self.path.stem
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
pytest tests/test_models.py -v
```
Expected: 3 个测试全部通过。

- [ ] **Step 5: 提交**

```bash
git add src/holle_music/models.py tests/test_models.py
git commit -m "feat: extend Song model with online source fields"
```

---

## Task 3: 实现 online_cache 缓存模块

**Files:**
- Create: `src/holle_music/online_cache.py`
- Test: `tests/test_online_cache.py`

- [ ] **Step 1: 编写缓存测试**

```python
# tests/test_online_cache.py
import json
import tempfile
from pathlib import Path

import pytest

from holle_music import online_cache as cache


@pytest.fixture
def tmp_cache(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setattr(cache, "CACHE_DIR", Path(td))
        yield Path(td)


def test_cache_dir_created(tmp_cache):
    d = cache.cache_dir()
    assert d.exists()


def test_audio_path_not_found(tmp_cache):
    assert cache.audio_path("BV000") is None


def test_audio_path_found(tmp_cache):
    (tmp_cache / "BV000_0.m4a").write_text("audio")
    assert cache.audio_path("BV000") == tmp_cache / "BV000_0.m4a"


def test_is_cached_skips_part_files(tmp_cache):
    (tmp_cache / "BV000_0.m4a.part").write_text("partial")
    assert cache.is_cached("BV000") is False


def test_save_and_load_metadata(tmp_cache):
    cache.save_metadata("BV000", {"title": "Test", "artist": "Artist"})
    meta = cache.load_metadata("BV000")
    assert meta["title"] == "Test"
    assert meta["artist"] == "Artist"
    assert "downloaded_at" in meta
    assert "last_played_at" in meta


def test_touch_updates_last_played(tmp_cache):
    cache.save_metadata("BV000", {"title": "Test"})
    old = cache.load_metadata("BV000")["last_played_at"]
    cache.touch("BV000")
    new = cache.load_metadata("BV000")["last_played_at"]
    assert new > old


def test_lru_cleanup_by_file_count(tmp_cache):
    for i in range(3):
        (tmp_cache / f"BV{i}_0.m4a").write_text("audio")
        cache.save_metadata(f"BV{i}", {"title": f"Song {i}"})
    # Make BV0 oldest, BV2 newest
    meta = cache.load_metadata("BV0")
    meta["last_played_at"] = 1
    (tmp_cache / "BV0.json").write_text(json.dumps(meta))

    cache.cleanup(max_mb=1024, max_files=2)
    assert not (tmp_cache / "BV0_0.m4a").exists()
    assert not (tmp_cache / "BV0.json").exists()
    assert (tmp_cache / "BV1_0.m4a").exists()
    assert (tmp_cache / "BV2_0.m4a").exists()


def test_clear(tmp_cache):
    (tmp_cache / "BV000_0.m4a").write_text("audio")
    cache.save_metadata("BV000", {"title": "Test"})
    cache.clear()
    assert len(list(tmp_cache.iterdir())) == 0


def test_cache_info(tmp_cache):
    (tmp_cache / "BV000_0.m4a").write_text("x" * 1024)
    info = cache.cache_info()
    assert info["file_count"] == 1
    assert info["size_mb"] == pytest.approx(0.001, abs=0.001)
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
pytest tests/test_online_cache.py -v
```
Expected: 因模块不存在而失败。

- [ ] **Step 3: 实现 `src/holle_music/online_cache.py`**

```python
"""Cache management for online audio sources."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from holle_music.settings import get_setting


CACHE_DIR = Path.home() / ".holle_music" / "cache" / "bilibili"
DEFAULT_MAX_MB = 1024
DEFAULT_MAX_FILES = 200


def _ensure_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def cache_dir() -> Path:
    """Return the cache directory, creating it if necessary."""
    _ensure_dir()
    return CACHE_DIR


def _metadata_path(bvid: str) -> Path:
    return CACHE_DIR / f"{bvid}.json"


def audio_path(bvid: str) -> Path | None:
    """Return cached audio path for bvid if fully downloaded, else None."""
    _ensure_dir()
    for p in CACHE_DIR.glob(f"{bvid}_0.*"):
        if p.suffix == ".part":
            continue
        if p.is_file() and p.stat().st_size > 0:
            return p
    return None


def is_cached(bvid: str) -> bool:
    return audio_path(bvid) is not None


def touch(bvid: str) -> None:
    """Update last_played_at timestamp for LRU."""
    meta = _metadata_path(bvid)
    if not meta.exists():
        return
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
        data["last_played_at"] = int(time.time())
        meta.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def save_metadata(bvid: str, metadata: dict[str, Any]) -> None:
    """Persist metadata for a cached bvid."""
    _ensure_dir()
    meta = _metadata_path(bvid)
    data = dict(metadata)
    data.setdefault("bvid", bvid)
    now = int(time.time())
    data.setdefault("downloaded_at", now)
    data.setdefault("last_played_at", now)
    meta.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load_metadata(bvid: str) -> dict[str, Any] | None:
    """Load metadata for a cached bvid, or None."""
    meta = _metadata_path(bvid)
    if not meta.exists():
        return None
    try:
        return json.loads(meta.read_text(encoding="utf-8"))
    except Exception:
        return None


def _cache_audio_files() -> list[Path]:
    _ensure_dir()
    return [
        p for p in CACHE_DIR.glob("*")
        if p.is_file() and p.suffix not in (".json", ".part")
    ]


def _cache_size_mb() -> float:
    files = _cache_audio_files()
    return sum(p.stat().st_size for p in files) / (1024 * 1024)


def _cache_file_count() -> int:
    return len(_cache_audio_files())


def _remove_bvid(bvid: str) -> None:
    for p in CACHE_DIR.glob(f"{bvid}*"):
        try:
            if p.is_file():
                p.unlink(missing_ok=True)
            elif p.is_dir():
                shutil.rmtree(p)
        except Exception:
            pass


def cleanup(max_mb: int | None = None, max_files: int | None = None) -> None:
    """LRU cleanup until cache is within limits."""
    _ensure_dir()
    max_mb = max_mb if max_mb is not None else DEFAULT_MAX_MB
    max_files = max_files if max_files is not None else DEFAULT_MAX_FILES

    while True:
        size_mb = _cache_size_mb()
        count = _cache_file_count()
        if size_mb <= max_mb and count <= max_files:
            break

        files: list[tuple[int, Path]] = []
        for p in _cache_audio_files():
            stem = p.stem.split("_")[0]
            meta = load_metadata(stem)
            last_played = meta.get("last_played_at", 0) if meta else 0
            files.append((last_played, p))

        if not files:
            break
        files.sort(key=lambda x: x[0])
        oldest_bvid = files[0][1].stem.split("_")[0]
        _remove_bvid(oldest_bvid)


def cleanup_from_settings() -> None:
    """Run cleanup using limits from user settings."""
    max_mb = get_setting("bilibili_cache_max_mb", DEFAULT_MAX_MB)
    max_files = get_setting("bilibili_cache_max_files", DEFAULT_MAX_FILES)
    cleanup(max_mb=int(max_mb), max_files=int(max_files))


def clear() -> None:
    """Remove all cached Bilibili audio and metadata."""
    _ensure_dir()
    for p in CACHE_DIR.glob("*"):
        try:
            if p.is_file():
                p.unlink(missing_ok=True)
            elif p.is_dir():
                shutil.rmtree(p)
        except Exception:
            pass


def cache_info() -> dict[str, Any]:
    """Return cache size and file count."""
    _ensure_dir()
    return {
        "size_mb": round(_cache_size_mb(), 2),
        "file_count": _cache_file_count(),
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
pytest tests/test_online_cache.py -v
```
Expected: 全部通过。

- [ ] **Step 5: 提交**

```bash
git add src/holle_music/online_cache.py tests/test_online_cache.py
git commit -m "feat: add online audio cache module with LRU cleanup"
```

---

## Task 4: 实现 bilibili_searcher 搜索与下载模块

**Files:**
- Create: `src/holle_music/bilibili_searcher.py`
- Test: `tests/test_bilibili_searcher.py`

- [ ] **Step 1: 编写搜索测试（mock DDGS + yt-dlp）**

```python
# tests/test_bilibili_searcher.py
from pathlib import Path
from unittest.mock import MagicMock, patch

from holle_music.bilibili_searcher import BilibiliSearcher, _extract_bvid
from holle_music.models import Song


def test_extract_bvid_from_url():
    assert _extract_bvid("https://www.bilibili.com/video/BV1xx411c7mD") == "BV1xx411c7mD"
    assert _extract_bvid("https://b23.tv/BV1xx411c7mD") == "BV1xx411c7mD"
    assert _extract_bvid("https://example.com") is None


def make_ddgs_result(href):
    return {"href": href}


def make_ydl_info(title, uploader="UP主", duration=180, thumbnails=None):
    return {
        "title": title,
        "uploader": uploader,
        "duration": duration,
        "thumbnails": thumbnails or [{"url": "https://cover.jpg"}],
    }


def test_search_parses_entries():
    searcher = BilibiliSearcher()

    ddgs_results = [
        make_ddgs_result("https://www.bilibili.com/video/BV1aaa"),
        make_ddgs_result("https://www.bilibili.com/video/BV1bbb"),
    ]

    def fake_ddgs(text, max_results):
        return ddgs_results

    mock_ydl = MagicMock()
    mock_ydl.extract_info.side_effect = [
        make_ydl_info("晴天"),
        make_ydl_info("七里香"),
    ]

    with patch("holle_music.bilibili_searcher.DDGS") as MockDDGS:
        MockDDGS.return_value.__enter__.return_value.text = fake_ddgs
        with patch("yt_dlp.YoutubeDL") as MockYD:
            MockYD.return_value.__enter__.return_value = mock_ydl
            results = searcher.search("周杰伦", max_results=2)

    assert len(results) == 2
    assert results[0].bvid == "BV1aaa"
    assert results[0].title == "晴天 (web)"
    assert results[0].source == "bilibili"


def test_search_returns_empty_on_no_results():
    searcher = BilibiliSearcher()

    def fake_ddgs(text, max_results):
        return []

    with patch("holle_music.bilibili_searcher.DDGS") as MockDDGS:
        MockDDGS.return_value.__enter__.return_value.text = fake_ddgs
        results = searcher.search("xxxxxxxxxxxx")

    assert results == []


def test_song_from_url_skips_invalid():
    searcher = BilibiliSearcher()
    assert searcher._song_from_url("https://example.com") is None
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
pytest tests/test_bilibili_searcher.py -v
```
Expected: 因模块不存在而失败。

- [ ] **Step 3: 实现 `src/holle_music/bilibili_searcher.py`**

```python
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


def _extract_bvid(url: str) -> str | None:
    """Extract bvid from a Bilibili video URL."""
    parsed = urlparse(url)
    if "bilibili.com" not in parsed.netloc:
        return None
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
        try:
            from ddgs import DDGS
        except ImportError as exc:
            raise RuntimeError("ddgs 未安装") from exc

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
        try:
            import yt_dlp
        except ImportError as exc:
            raise RuntimeError("yt-dlp 未安装") from exc

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
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
pytest tests/test_bilibili_searcher.py -v
```
Expected: 全部通过。

- [ ] **Step 5: 提交**

```bash
git add src/holle_music/bilibili_searcher.py tests/test_bilibili_searcher.py
git commit -m "feat: add Bilibili search and audio download module"
```

---

## Task 5: 更新默认设置

**Files:**
- Modify: `src/holle_music/settings.py`

- [ ] **Step 1: 在 `DEFAULT_SETTINGS` 中增加缓存配置**

```python
DEFAULT_SETTINGS: dict[str, Any] = {
    "color": "pink",
    "volume": 1.0,
    "music_dir": "E:/Music",
    "play_mode": "sequential",
    "main_color": "light",
    "current_song_path": "",
    "current_song_title": "",
    "bilibili_cache_max_mb": 1024,
    "bilibili_cache_max_files": 200,
}
```

- [ ] **Step 2: 运行现有设置测试确认无回归**

Run:
```bash
pytest tests/test_settings.py -v
```
Expected: 全部通过。

- [ ] **Step 3: 提交**

```bash
git add src/holle_music/settings.py
git commit -m "feat: add default Bilibili cache limits to settings"
```

---

## Task 6: 在 TUI 中集成 `/search` 与 `/cache` 命令

**Files:**
- Modify: `src/holle_music/app.py`

- [ ] **Step 1: 在 `CommandType` 和 `COMMAND_MAP` 中新增 `CACHE`**

```python
class CommandType(Enum):
    ...
    CACHE = auto()
    ...

COMMAND_MAP = {
    ...
    "/cache": CommandType.CACHE,
    "cache": CommandType.CACHE,
    ...
}
```

- [ ] **Step 2: 在 `HolleMusicApp.__init__` 中初始化搜索器与下载线程池**

```python
from holle_music.bilibili_searcher import BilibiliSearcher, is_network_error
from holle_music.online_cache import (
    audio_path,
    cache_info,
    clear as clear_cache,
    is_cached,
)

class HolleMusicApp(App):
    def __init__(self) -> None:
        ...
        self._bilibili_searcher = BilibiliSearcher(progress_callback=lambda msg: self.call_from_thread(lambda: self._notify_chat(msg)))
        self._online_download_pool: list[threading.Thread] = []
        self._online_search_thread: threading.Thread | None = None
```

- [ ] **Step 3: 修改 `_search_songs` 支持 B 站 fallback**

```python
def _search_songs(self, query: str) -> None:
    q = query.strip().lower()
    all_songs = self._original_songs or self.player.playlist

    if not q:
        self._restore_playlist_display()
        return

    results = [s for s in all_songs if q in s.title.lower() or q in s.artist.lower()]
    if results:
        self._displayed_songs = results
        self.player.load_playlist(results)
        panel = self.query_one("#playlist-panel", PlaylistPanel)
        panel.load_songs(results)
        panel.border_title = f'✻ Playlist | 搜索: "{query}"'
        self._notify_chat(f'搜索 "{query}" — {len(results)} 首')
        return

    # Local empty: search Bilibili.
    self._cancel_online_search()
    self._notify_chat(f'本地未找到 "{query}"，正在搜索 Bilibili...')

    def _do_search():
        try:
            songs = self._bilibili_searcher.search(query, max_results=10)
            if not songs:
                self.call_from_thread(
                    lambda: self._notify_chat(f'本地和 B 站都未找到 "{query}"')
                )
                return
            self.call_from_thread(lambda: self._on_bilibili_results(query, songs))
        except Exception as exc:
            msg = "无法连接网络搜索 B 站" if is_network_error(exc) else f"B 站搜索失败: {exc}"
            self.call_from_thread(lambda: self._notify_chat(f'本地未找到 "{query}"，{msg}。'))

    self._online_search_thread = threading.Thread(target=_do_search, daemon=True)
    self._online_search_thread.start()
```

- [ ] **Step 4: 新增 B 站结果展示与后台下载方法**

```python
def _on_bilibili_results(self, query: str, songs: list[Song]) -> None:
    self._displayed_songs = list(songs)
    self.player.load_playlist(songs)
    panel = self.query_one("#playlist-panel", PlaylistPanel)
    panel.load_songs(songs)
    panel.border_title = f'✻ Playlist | B站: "{query}"'
    self._notify_chat(f'B站搜索 "{query}" — {len(songs)} 首（正在后台下载）')
    self._download_online_songs(songs)


def _download_online_songs(self, songs: list[Song], concurrency: int = 3) -> None:
    """Download Bilibili songs in background with limited concurrency."""
    self._cancel_online_downloads()
    sem = threading.Semaphore(concurrency)

    def _download_one(song: Song) -> None:
        with sem:
            try:
                self._bilibili_searcher.download_audio(song)
                cached = audio_path(song.bvid)
                if cached:
                    song.path = cached
                    self.call_from_thread(lambda: self._notify_chat(f"{song.title} 下载完成"))
            except Exception as exc:
                msg = "下载失败，请检查网络" if is_network_error(exc) else str(exc)
                self.call_from_thread(lambda: self._notify_chat(f"{song.title} {msg}"))

    for song in songs:
        t = threading.Thread(target=_download_one, args=(song,), daemon=True)
        self._online_download_pool.append(t)
        t.start()

def _cancel_online_search(self) -> None:
    if self._bilibili_searcher is not None:
        self._bilibili_searcher.cancel()

def _cancel_online_downloads(self) -> None:
    # Running download threads are daemon and will finish or be killed on exit.
    # We only clear the tracking list here; cancellation of active yt-dlp downloads
    # is best-effort for this version.
    self._online_download_pool.clear()
```

- [ ] **Step 5: 修改 `on_list_view_highlighted` 处理未下载的在线歌曲**

```python
def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
    ...
    song = songs[idx]

    if song.source == "bilibili":
        if not is_cached(song.bvid):
            self._notify_chat(f"{song.title} 正在下载中...")
            return
        cached = audio_path(song.bvid)
        if cached:
            song.path = cached

    self.player.play(song)
    self._update_controls_ui()
```

- [ ] **Step 6: 在 `_handle_command` 中处理 `CACHE` 命令**

```python
elif cmd.type == CommandType.CACHE:
    arg = (cmd.args or "").strip().lower()
    if arg in ("clear", "清空"):
        clear_cache()
        self._notify_chat("已清空 B 站缓存")
    else:
        info = cache_info()
        self._notify_chat(f"B 站缓存: {info['size_mb']} MB，{info['file_count']} 个文件")
```

- [ ] **Step 7: 修改 `_write_pet_state` 避免空 path 问题**

在 `app.py` 的 `_write_pet_state` 中，当 song.path 为空时序列化为空字符串即可（当前已是这样）。无需额外修改，但确保 `Song.path` 是 `Path("")` 时 `str()` 为空字符串。

- [ ] **Step 8: 运行应用 smoke test**

Run:
```bash
python -m holle_music.app
```
手动验证：
- 启动后输入 `/search 晴天`
- 如果本地无结果，应看到 B 站搜索提示。
按 `ctrl+c` 退出。

- [ ] **Step 9: 提交**

```bash
git add src/holle_music/app.py
git commit -m "feat: integrate Bilibili search and cache commands into TUI"
```

---

## Task 7: 扩展 TUI AI 工具

**Files:**
- Modify: `src/holle_music/tui_tools.py`

- [ ] **Step 1: 新增 `search_bilibili` 工具**

在 `tui_tools.py` 的 `TUITools` 类中新增：

```python
from holle_music.bilibili_searcher import BilibiliSearcher, is_network_error

class TUITools:
    def __init__(self, app: Any) -> None:
        self._app = app
        self._last_search_results: list[Song] = []
        self._last_bilibili_results: list[Song] = []

    def _tool_search_bilibili(self, args: dict) -> str:
        """Search Bilibili for audio."""
        query = args.get("query", "").strip()
        if not query:
            return "搜索关键词为空"

        try:
            searcher = BilibiliSearcher()
            songs = searcher.search(query, max_results=args.get("max_results", 10))
        except Exception as exc:
            return "无法连接网络搜索 B 站" if is_network_error(exc) else f"B 站搜索失败: {exc}"

        self._last_bilibili_results = songs
        self._last_search_results = songs

        if not songs:
            return f'B 站未找到 "{query}"'

        lines = [f'B站搜索 "{query}" 结果 ({len(songs)} 首):']
        for i, song in enumerate(songs[:10], 1):
            lines.append(f"{i}. {song.title} - {song.artist}")
        if len(songs) > 10:
            lines.append(f"... 还有 {len(songs) - 10} 首")
        lines.append("如果用户想播放其中一首，请调用 play_song 工具实际播放。")
        return "\n".join(lines)
```

- [ ] **Step 2: 修改 `play_song` 支持 B 站结果**

```python
def _tool_play_song(self, args: dict) -> str:
    title = args.get("title", "").strip()
    artist = args.get("artist", "").strip()
    if not title:
        return "歌曲标题为空"

    # Try Bilibili results first.
    for song in self._last_bilibili_results:
        s_title = (song.title or "").strip()
        s_artist = (song.artist or "").strip()
        if title.lower() in s_title.lower():
            if not artist or artist.lower() in s_artist.lower():
                return self._play_bilibili_song(song)

    # Then local results.
    for song in self._last_search_results:
        if title.lower() in (song.title or "").lower():
            if not artist or artist.lower() in (song.artist or "").lower():
                self._app.player.play(song)
                self._app._update_controls_ui()
                self._app._sync_playlist_selection()
                return f"正在播放: {song.title} - {song.artist}"

    # Fall back to full playlist.
    songs = list(self._app._original_songs or self._app.player.playlist or [])
    for song in songs:
        if title.lower() in (song.title or "").lower():
            if not artist or artist.lower() in (song.artist or "").lower():
                self._app.player.play(song)
                self._app._update_controls_ui()
                self._app._sync_playlist_selection()
                return f"正在播放: {song.title} - {song.artist}"

    return f"未找到歌曲: {title}" + (f" - {artist}" if artist else "")


def _play_bilibili_song(self, song: Song) -> str:
    from holle_music.online_cache import audio_path, is_cached

    if is_cached(song.bvid):
        cached = audio_path(song.bvid)
        song.path = cached
        self._app.player.play(song)
        self._app._update_controls_ui()
        self._app._sync_playlist_selection()
        return f"正在播放: {song.title} - {song.artist}"

    self._app._notify_chat(f"{song.title} 正在下载...")

    def _download_and_play():
        try:
            searcher = BilibiliSearcher(progress_callback=self._app._notify_chat)
            cached = searcher.download_audio(song)
            song.path = cached
            self._app.call_from_thread(lambda: (
                self._app.player.play(song),
                self._app._update_controls_ui(),
                self._app._sync_playlist_selection(),
                self._app._notify_chat(f"正在播放: {song.title} - {song.artist}"),
            ))
        except Exception as exc:
            msg = "下载失败，请检查网络" if is_network_error(exc) else str(exc)
            self._app.call_from_thread(lambda: self._app._notify_chat(f"{song.title} {msg}"))

    threading.Thread(target=_download_and_play, daemon=True).start()
    return f"正在准备播放: {song.title} - {song.artist}"
```

- [ ] **Step 3: 更新系统提示（在 `app.py` 的 `_chat_with_ai` 附近）**

在构造给 tool-calling AI 的 prompt 中增加：

```python
prompt_parts.append(
    "如果用户想找的歌本地没有，请调用 search_bilibili 工具搜索 B 站。"
    "B 站结果在播放列表中带有 '(web)' 标记。"
    "如果用户说'播放'，找到结果后必须调用 play_song；如果用户说'搜索'，只返回结果不播放。"
)
```

- [ ] **Step 4: 运行测试**

Run:
```bash
pytest tests/test_tui_tools.py -v 2>/dev/null || echo "no existing tests"
python -m compileall src/holle_music/tui_tools.py
```
Expected: 编译通过，无语法错误。

- [ ] **Step 5: 提交**

```bash
git add src/holle_music/tui_tools.py src/holle_music/app.py
git commit -m "feat: add search_bilibili tool and Bilibili playback to TUI AI"
```

---

## Task 8: 扩展 Pet `/search` 命令

**Files:**
- Modify: `src/holle_music/pet/commands.py`

- [ ] **Step 1: 修改 `_cmd_search` 支持 B 站 fallback**

```python
def _cmd_search(self, arg: str) -> str:
    query = arg.strip()
    if not query:
        return "请输入搜索关键词，例如 /search 周杰伦"

    # Try local first.
    result = self._tools.execute("search_local", {"query": query})
    if result and not result.startswith("本地未找到"):
        return result

    # Fallback to Bilibili.
    return self._tools.execute("search_bilibili", {"query": query})
```

- [ ] **Step 2: 运行 Pet 命令 smoke test**

Run:
```bash
python -m compileall src/holle_music/pet/commands.py
```
Expected: 编译通过。

- [ ] **Step 3: 提交**

```bash
git add src/holle_music/pet/commands.py
git commit -m "feat: extend pet /search with Bilibili fallback"
```

---

## Task 9: 扩展 Pet AI 工具

**Files:**
- Modify: `src/holle_music/pet/ai_tools.py`

- [ ] **Step 1: 在 `AITools.__init__` 中新增 bilibili 结果缓存**

```python
def __init__(self, player: Any, window: Any = None) -> None:
    self._player = player
    self._window = window
    self._last_search_results: list[dict] = []
    self._last_bilibili_results: list[Song] = []
```

- [ ] **Step 2: 新增 `search_bilibili` 工具**

```python
from holle_music.bilibili_searcher import BilibiliSearcher, is_network_error
from holle_music.models import Song

def _tool_search_bilibili(self, args: dict) -> str:
    """Search Bilibili for audio."""
    query = args.get("query", "").strip()
    if not query:
        return "搜索关键词为空"

    try:
        searcher = BilibiliSearcher()
        songs = searcher.search(query, max_results=args.get("max_results", 10))
    except Exception as exc:
        return "无法连接网络搜索 B 站" if is_network_error(exc) else f"B 站搜索失败: {exc}"

    self._last_bilibili_results = songs
    self._last_search_results = songs

    if not songs:
        return f'B 站未找到 "{query}"'

    lines = [f'B站搜索 "{query}" 结果 ({len(songs)} 首):']
    for i, song in enumerate(songs[:10], 1):
        lines.append(f"{i}. {song.title} - {song.artist}")
    if len(songs) > 10:
        lines.append(f"... 还有 {len(songs) - 10} 首")
    lines.append("如果用户想播放其中一首，请调用 play_song 工具实际播放。")
    return "\n".join(lines)
```

- [ ] **Step 3: 修改 `play_song` 支持 B 站**

```python
def _tool_play_song(self, args: dict) -> str:
    title = args.get("title", "").strip()
    artist = args.get("artist", "").strip()
    if not title:
        return "歌曲标题为空"

    # Try Bilibili results first.
    for song in self._last_bilibili_results:
        s_title = (song.title or "").strip()
        s_artist = (song.artist or "").strip()
        if title.lower() in s_title.lower():
            if not artist or artist.lower() in s_artist.lower():
                return self._play_bilibili_song(song)

    # Existing local fallback...
    for song in self._last_search_results:
        s_title = (song.get("title") or "").strip()
        s_artist = (song.get("artist") or "").strip()
        if title.lower() in s_title.lower():
            if not artist or artist.lower() in s_artist.lower():
                self._player.play_song(song)
                return f"正在播放: {s_title} - {s_artist}"

    payload = {"title": title}
    if artist:
        payload["artist"] = artist
    self._player.play_song(payload)
    return f"尝试播放: {title}" + (f" - {artist}" if artist else "")


def _play_bilibili_song(self, song: Song) -> str:
    from holle_music.online_cache import audio_path, is_cached

    if is_cached(song.bvid):
        cached = audio_path(song.bvid)
        song.path = cached
        self._player.play_song({
            "path": str(cached),
            "title": song.title,
            "artist": song.artist,
            "duration": song.duration,
            "source": song.source,
            "bvid": song.bvid,
        })
        return f"正在播放: {song.title} - {song.artist}"

    self._window.show_response_bubble(f"{song.title} 正在下载...")

    def _download_and_play():
        try:
            searcher = BilibiliSearcher()
            cached = searcher.download_audio(song)
            song.path = cached
            self._player.play_song({
                "path": str(cached),
                "title": song.title,
                "artist": song.artist,
                "duration": song.duration,
                "source": song.source,
                "bvid": song.bvid,
            })
            self._window.show_response_bubble(f"正在播放: {song.title} - {song.artist}")
        except Exception as exc:
            msg = "下载失败，请检查网络" if is_network_error(exc) else str(exc)
            self._window.show_response_bubble(f"{song.title} {msg}")

    threading.Thread(target=_download_and_play, daemon=True).start()
    return f"正在准备播放: {song.title} - {song.artist}"
```

- [ ] **Step 4: 运行编译检查**

Run:
```bash
python -m compileall src/holle_music/pet/ai_tools.py
```
Expected: 编译通过。

- [ ] **Step 5: 提交**

```bash
git add src/holle_music/pet/ai_tools.py
git commit -m "feat: add Bilibili search and playback to pet AI tools"
```

---

## Task 10: 运行全量测试并修复回归

**Files:**
- 所有已修改文件

- [ ] **Step 1: 运行全量测试**

Run:
```bash
pytest tests/ -v
```
Expected: 新增测试通过；已有测试无回归。

- [ ] **Step 2: 如有失败，定位并修复**

常见回归点：
- `Song` 新增字段导致旧测试断言失败 → 更新测试。
- `app.py` 导入新模块导致循环导入 → 检查导入顺序。
- Pet IPC 序列化 `Path("")` → 确保 `str(Path(""))` 为 `""`。

- [ ] **Step 3: 提交修复**

```bash
git add .
git commit -m "fix: resolve test regressions for Bilibili feature"
```

---

## Task 11: 更新 README 与帮助文本

**Files:**
- Modify: `README.md`
- Modify: `src/holle_music/app.py`（`/help` 命令）
- Modify: `src/holle_music/pet/commands.py`（`_cmd_help`）

- [ ] **Step 1: 更新 `README.md` 功能说明**

在功能特点中新增：

```markdown
- 🔍 B 站音频搜索（`/search` 本地无结果时自动搜索 Bilibili）
- 💾 B 站在线音频缓存与自动清理
```

在命令列表中更新 `/search` 说明：

```markdown
| `/search <关键词>` | 搜索本地歌曲，无结果时自动搜索 B 站音频 |
| `/cache` | 查看 B 站缓存占用 |
| `/cache clear` | 清空 B 站缓存 |
```

- [ ] **Step 2: 更新 TUI `/help` 输出**

在 `app.py` `_handle_command` 的 HELP 分支中：

```python
"/search <关键词>  搜索本地歌曲，无结果时搜索 B 站\n"
"/cache            查看 B 站缓存\n"
"/cache clear      清空 B 站缓存\n"
```

- [ ] **Step 3: 更新 Pet `/help` 输出**

在 `pet/commands.py` `_cmd_help` 中：

```python
"/search <关键词> 搜索本地歌曲，无结果时搜索 B 站\n"
"/cache 查看 B 站缓存 | /cache clear 清空缓存\n"
```

- [ ] **Step 4: 提交**

```bash
git add README.md src/holle_music/app.py src/holle_music/pet/commands.py
git commit -m "docs: update help text and README for Bilibili audio feature"
```

---

## Task 12: 更新项目记忆文件

**Files:**
- Create: `memory/modules/bilibili_searcher.md`
- Create: `memory/modules/online_cache.md`
- Modify: `memory/_index.md`
- Modify: `memory/modules/commands.md`
- Modify: `memory/modules/pet.md`

- [ ] **Step 1: 创建 `memory/modules/bilibili_searcher.md`**

```markdown
---
name: project_bilibili_searcher
description: Bilibili 音频搜索与下载模块
metadata:
  type: project
---

# bilibili_searcher 模块

`src/holle_music/bilibili_searcher.py` —— 负责 Bilibili 视频搜索、音频流解析与下载。

## 核心接口

| 名称 | 签名 | 说明 |
|---|---|---|
| `BilibiliSearcher` | class | 搜索与下载入口。 |
| `search(query, max_results=10)` | method | 返回 `list[Song]`，每个 Song 的 `source="bilibili"`。 |
| `download_audio(song)` | method | 下载音频到缓存，返回本地 `Path`。 |
| `cancel()` | method | 取消正在进行的搜索/下载。 |
| `is_network_error(exc)` | function | 判断异常是否为网络错误。 |

## 变更历史

- **2026-06-22**: 创建模块，支持 B 站搜索与音频下载，供 TUI 和 Pet 共用。
```

- [ ] **Step 2: 创建 `memory/modules/online_cache.md`**

```markdown
---
name: project_online_cache
description: 在线音频缓存管理模块，含 LRU 清理
type: project
---

# online_cache 模块

`src/holle_music/online_cache.py` —— 管理 Bilibili 音频缓存目录、命中查询、LRU 自动清理与手动清理。

## 核心接口

| 名称 | 签名 | 说明 |
|---|---|---|
| `cache_dir()` | function | 返回并创建缓存目录。 |
| `audio_path(bvid)` | function | 返回已缓存音频路径或 `None`。 |
| `is_cached(bvid)` | function | 是否已缓存。 |
| `save_metadata(bvid, metadata)` | function | 保存/更新元数据。 |
| `touch(bvid)` | function | 更新 `last_played_at`。 |
| `cleanup(max_mb, max_files)` | function | LRU 清理。 |
| `cleanup_from_settings()` | function | 按 `settings.json` 配置清理。 |
| `clear()` | function | 清空缓存。 |
| `cache_info()` | function | 返回缓存大小和文件数。 |

## 配置项

- `bilibili_cache_max_mb`：默认 1024
- `bilibili_cache_max_files`：默认 200

## 变更历史

- **2026-06-22**: 创建模块，支持 B 站音频缓存 LRU 管理。
```

- [ ] **Step 3: 更新 `memory/_index.md`**

在模块表中新增两行：

```markdown
| bilibili_searcher | [`modules/bilibili_searcher.md`](modules/bilibili_searcher.md) | 开发中 | 2026-06-22 | Bilibili 音频搜索与下载 |
| online_cache | [`modules/online_cache.md`](modules/online_cache.md) | 开发中 | 2026-06-22 | 在线音频缓存 LRU 管理 |
```

- [ ] **Step 4: 更新 `memory/modules/commands.md` 变更历史**

追加：

```markdown
- **2026-06-22**: 扩展 `/search`：本地无结果时自动搜索 Bilibili；新增 `/cache` / `/cache clear` 命令。
```

- [ ] **Step 5: 更新 `memory/modules/pet.md` 变更历史**

追加：

```markdown
- **2026-06-22**: Pet `/search` 与 AI 工具新增 Bilibili fallback，支持在线音频搜索与播放。
```

- [ ] **Step 6: 提交**

```bash
git add memory/
git commit -m "docs: add memory entries for bilibili_searcher and online_cache modules"
```

---

## Task 13: 集成验证

**Files:**
- 全部

- [ ] **Step 1: 终端验证**

Run:
```bash
python -m holle_music.app
```

手动执行：
1. 确保本地歌单没有“晴天”。
2. 输入 `/search 晴天`。
3. 观察到提示“正在搜索 Bilibili...”。
4. 列表出现带 `(web)` 的结果，后台开始下载。
5. 等待某条下载完成后点击，确认能播放。
6. 输入 `/cache`，确认显示缓存大小。
7. 输入 `/cache clear`，确认缓存清空。
8. 输入 `/help`，确认命令说明已更新。

- [ ] **Step 2: Pet 验证**

Run:
```bash
python -m holle_music.pet.main
```

手动执行：
1. 在宠物输入框输入 `/search 晴天`。
2. 观察气泡返回 B 站搜索结果。
3. 输入“播放第一个”，确认开始下载并播放。

- [ ] **Step 3: 最终提交**

```bash
git add .
git commit -m "feat: complete Bilibili online audio search and playback for v0.4.0-beta"
```

---

## 自我检查

### Spec 覆盖

| Spec 要求 | 对应任务 |
|---|---|
| Bilibili 搜索 | Task 4 |
| 下载到缓存后播放 | Task 3, Task 4, Task 6 |
| `/search` 本地优先 fallback | Task 6, Task 8 |
| `(web)` 标记 | Task 4 |
| 10 条结果后台下载 | Task 6 |
| AI 智能播放/搜索 | Task 7, Task 9 |
| LRU 缓存清理 | Task 3, Task 5 |
| `/cache` / `/cache clear` | Task 3, Task 6 |
| 网络错误提示 | Task 4, Task 6, Task 7, Task 9 |
| 测试 | Task 2, 3, 4, 10 |
| README / 记忆 | Task 11, 12 |

### Placeholder 检查

- 无 TBD/TODO。
- 所有代码步骤包含实际代码。
- 所有命令包含预期输出。

### 类型一致性

- `Song` 字段：`source`, `bvid`, `web_url`, `cover_url` 在 Task 2 定义，后续任务一致使用。
- `audio_path(bvid)` 返回 `Path | None`。
- `BilibiliSearcher.search()` 返回 `list[Song]`。
