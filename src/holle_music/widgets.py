"""Textual custom widgets for Holle Music player.

Widgets:
    AlbumCover  — Square panel with white border, shows album art placeholder.
    LyricsPanel — Rectangular panel with white border, shows lyrics.
    PlaylistPanel — Tall panel with white border, scrollable song list.
"""

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Static, ListView, ListItem, Button, Input, Label


class AlbumCover(Static):
    """专辑封面面板 — 带白色边框，居中显示占位符."""

    BORDER_TITLE = "专辑封面"

    def compose(self) -> ComposeResult:
        yield Static("暂无封面", id="album-art-placeholder")

    def on_mount(self) -> None:
        self.styles.border = ("solid", "white")
        self.styles.content_align = ("center", "middle")

    def set_cover_text(self, text: str) -> None:
        placeholder = self.query_one("#album-art-placeholder", Static)
        placeholder.update(text)


class LyricsPanel(Static):
    """歌词面板 — 带白色边框，居中显示歌词."""

    BORDER_TITLE = "歌词"

    def compose(self) -> ComposeResult:
        yield Static("暂无歌词", id="lyrics-content")

    def on_mount(self) -> None:
        self.styles.border = ("solid", "white")
        self.styles.content_align = ("center", "middle")
        self.styles.overflow_y = "auto"

    def set_lyrics(self, text: str) -> None:
        content = self.query_one("#lyrics-content", Static)
        content.update(text)


class PlaylistPanel(Static):
    """播放列表面板 — 带白色边框，支持列表滚动."""

    BORDER_TITLE = "播放列表"

    def compose(self) -> ComposeResult:
        yield Static("暂无歌曲", id="playlist-placeholder")
        yield ListView(id="playlist-list")

    def on_mount(self) -> None:
        self.styles.border = ("solid", "white")
        self._hide_placeholder(False)

    def _hide_placeholder(self, hidden: bool) -> None:
        placeholder = self.query_one("#playlist-placeholder", Static)
        lst = self.query_one("#playlist-list", ListView)
        placeholder.display = False if hidden else True
        lst.display = True if hidden else False

    def load_songs(self, songs: list) -> None:
        """加载歌曲列表，每首歌曲作为 ListItem."""
        lst = self.query_one("#playlist-list", ListView)
        lst.clear()
        if not songs:
            self._hide_placeholder(False)
            return
        self._hide_placeholder(True)
        for song in songs:
            label = f"{song.title}  —  {song.artist}"
            lst.append(ListItem(Static(label)))

    def get_selected_index(self) -> int | None:
        """返回当前选中的歌曲索引."""
        lst = self.query_one("#playlist-list", ListView)
        return lst.index if lst.index is not None else None
