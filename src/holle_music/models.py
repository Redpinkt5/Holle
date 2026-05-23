"""Holle Music 数据模型."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(eq=False)
class Song:
    """一首歌曲."""

    path: Path
    title: str = ""
    artist: str = "未知艺术家"
    album: str = "未知专辑"
    duration: float = 0.0

    def __post_init__(self):
        if isinstance(self.path, str):
            self.path = Path(self.path)
        if not self.title:
            self.title = self.path.stem

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Song):
            return NotImplemented
        return self.path == other.path

    def __hash__(self) -> int:
        return hash(self.path)


class Playlist:
    """歌单，包含多首歌曲."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._songs: list[Song] = []

    @property
    def songs(self) -> list[Song]:
        return list(self._songs)

    def add_song(self, song: Song) -> None:
        if song not in self._songs:
            self._songs.append(song)

    def remove_song(self, song: Song) -> None:
        if song in self._songs:
            self._songs.remove(song)

    def __iter__(self):
        return iter(self._songs)

    def __len__(self) -> int:
        return len(self._songs)
