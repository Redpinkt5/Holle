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
        now = int(time.time())
        last_played = data.get("last_played_at", 0)
        if last_played >= now:
            data["last_played_at"] = last_played + 1
        else:
            data["last_played_at"] = now
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
