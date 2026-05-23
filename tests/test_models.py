"""Tests for Song and Playlist models."""

from pathlib import Path
from holle_music.models import Song, Playlist


class TestSong:
    def test_create_song_with_minimal_fields(self):
        song = Song(path=Path("/music/test.mp3"))
        assert song.path == Path("/music/test.mp3")
        assert song.title == "test"  # inferred from filename
        assert song.artist == "未知艺术家"
        assert song.album == "未知专辑"
        assert song.duration == 0.0

    def test_create_song_with_all_fields(self):
        song = Song(
            path=Path("/music/song.flac"),
            title="测试歌曲",
            artist="测试歌手",
            album="测试专辑",
            duration=245.5,
        )
        assert song.title == "测试歌曲"
        assert song.artist == "测试歌手"
        assert song.album == "测试专辑"
        assert song.duration == 245.5

    def test_song_title_from_filename(self):
        song = Song(path=Path("/music/周杰伦 - 晴天.mp3"))
        assert song.title == "周杰伦 - 晴天"

    def test_song_equality(self):
        s1 = Song(path=Path("/a.mp3"))
        s2 = Song(path=Path("/a.mp3"))
        s3 = Song(path=Path("/b.mp3"))
        assert s1 == s2
        assert s1 != s3


class TestPlaylist:
    def test_create_empty_playlist(self):
        pl = Playlist(name="我的歌单")
        assert pl.name == "我的歌单"
        assert len(pl.songs) == 0

    def test_add_song_to_playlist(self):
        pl = Playlist(name="测试")
        song = Song(path=Path("/music/a.mp3"))
        pl.add_song(song)
        assert len(pl.songs) == 1
        assert pl.songs[0] == song

    def test_remove_song_from_playlist(self):
        pl = Playlist(name="测试")
        song = Song(path=Path("/music/a.mp3"))
        pl.add_song(song)
        pl.remove_song(song)
        assert len(pl.songs) == 0

    def test_playlist_iteration(self):
        pl = Playlist(name="测试")
        songs = [
            Song(path=Path(f"/music/{i}.mp3"))
            for i in range(3)
        ]
        for s in songs:
            pl.add_song(s)
        assert list(pl) == songs
        assert len(pl) == 3
