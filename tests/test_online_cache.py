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
