"""Tests for music file scanner."""

import tempfile
from pathlib import Path
from holle_music.scanner import Scanner
from holle_music.models import Song


class TestScanner:
    def test_scan_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            scanner = Scanner()
            songs = scanner.scan(Path(tmp))
            assert songs == []

    def test_scan_directory_with_mp3_files(self, tmp_path: Path):
        (tmp_path / "song1.mp3").touch()
        (tmp_path / "song2.mp3").touch()
        (tmp_path / "not_music.txt").touch()

        scanner = Scanner()
        songs = scanner.scan(tmp_path)

        assert len(songs) == 2
        titles = {s.title for s in songs}
        assert titles == {"song1", "song2"}

    def test_scan_supports_flac_and_wav(self, tmp_path: Path):
        (tmp_path / "a.flac").touch()
        (tmp_path / "b.wav").touch()
        (tmp_path / "c.ogg").touch()

        scanner = Scanner()
        songs = scanner.scan(tmp_path)

        assert len(songs) == 2  # ogg not supported
        extensions = {s.path.suffix for s in songs}
        assert extensions == {".flac", ".wav"}

    def test_scan_recursive_directories(self, tmp_path: Path):
        (tmp_path / "rock").mkdir()
        (tmp_path / "rock" / "song.mp3").touch()
        (tmp_path / "jazz").mkdir()
        (tmp_path / "jazz" / "tune.flac").touch()

        scanner = Scanner()
        songs = scanner.scan(tmp_path)

        assert len(songs) == 2

    def test_scan_to_playlist(self, tmp_path: Path):
        (tmp_path / "test.mp3").touch()

        scanner = Scanner()
        playlist = scanner.scan_to_playlist(tmp_path, name="我的音乐")

        assert playlist.name == "我的音乐"
        assert len(playlist) == 1
        assert playlist.songs[0].title == "test"

    def test_supported_extensions(self):
        scanner = Scanner()
        exts = scanner.supported_extensions
        assert ".mp3" in exts
        assert ".flac" in exts
        assert ".wav" in exts
