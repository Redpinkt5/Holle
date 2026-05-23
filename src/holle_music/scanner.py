"""音乐文件扫描器 — 递归扫描目录，发现 MP3/FLAC/WAV 文件."""

from pathlib import Path
from holle_music.models import Song, Playlist


class Scanner:
    """本地音乐文件扫描器."""

    SUPPORTED_EXTENSIONS: set[str] = {".mp3", ".flac", ".wav"}

    @property
    def supported_extensions(self) -> set[str]:
        return self.SUPPORTED_EXTENSIONS

    def scan(self, directory: Path) -> list[Song]:
        """递归扫描目录，返回发现的歌曲列表."""
        if isinstance(directory, str):
            directory = Path(directory)
        if not directory.is_dir():
            return []

        songs: list[Song] = []
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                song = self._create_song(path)
                songs.append(song)
        return sorted(songs, key=lambda s: s.title)

    def scan_to_playlist(self, directory: Path, name: str | None = None) -> Playlist:
        """扫描目录并以歌单形式返回."""
        songs = self.scan(directory)
        playlist_name = name or directory.name
        playlist = Playlist(name=playlist_name)
        for song in songs:
            playlist.add_song(song)
        return playlist

    def _create_song(self, path: Path) -> Song:
        """从文件路径创建 Song，尝试读取元数据."""
        song = Song(path=path)
        try:
            import mutagen
            audio = mutagen.File(str(path))
            if audio is not None:
                tags = getattr(audio, "tags", None)
                if tags is not None:
                    song.title = tags.get("title", [song.title])[0] or song.title
                    song.artist = tags.get("artist", [song.artist])[0] or song.artist
                    song.album = tags.get("album", [song.album])[0] or song.album
                info = getattr(audio, "info", None)
                if info is not None:
                    song.duration = info.length
        except ImportError:
            pass
        except Exception:
            pass
        return song
