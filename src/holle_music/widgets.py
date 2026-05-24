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


class Controls(Container):
    """播放控制面板 — 无外边框，上一曲/播放暂停/下一曲 + 歌曲信息按钮."""

    def compose(self) -> ComposeResult:
        with Container(id="controls-buttons"):
            yield Button("◀  上一曲", id="btn-prev", variant="default")
            yield Button("⏸  播放/暂停", id="btn-play-pause", variant="default")
            yield Button("▶  下一曲", id="btn-next", variant="default")
        with Container(id="controls-info"):
            yield Button("歌曲信息", id="btn-song-info", variant="default")

    def on_mount(self) -> None:
        buttons_row = self.query_one("#controls-buttons", Container)
        buttons_row.styles.layout = "horizontal"
        buttons_row.styles.align = ("center", "middle")
        buttons_row.styles.content_align = ("center", "middle")
        info_row = self.query_one("#controls-info", Container)
        info_row.styles.align = ("center", "middle")
        info_row.styles.content_align = ("center", "middle")
        self.styles.align = ("center", "middle")

    def set_play_pause_label(self, is_playing: bool) -> None:
        btn = self.query_one("#btn-play-pause", Button)
        btn.label = "⏸  暂停" if is_playing else "▶  播放"


class Visualizer(Static):
    """歌曲律动面板 — ASCII 条形频谱可视化，跟随真实音频频率."""

    BORDER_TITLE = "歌曲律动"

    _bars: int = 32
    _timer_handle: object | None = None
    _get_spectrum: object = None  # callable returning list[float]

    def compose(self) -> ComposeResult:
        yield Static("", id="viz-content")

    def on_mount(self) -> None:
        self.styles.border = ("solid", "white")
        self.styles.content_align = ("center", "middle")
        self.styles.padding = 0

    def set_spectrum_source(self, source) -> None:
        """设置频谱数据源 (callable, 返回 32 个频段值)."""
        self._get_spectrum = source

    def start(self) -> None:
        """启动频谱动画定时器."""
        self._timer_handle = self.set_interval(0.08, self._update_bars)

    def stop(self) -> None:
        """停止频谱动画."""
        if self._timer_handle is not None:
            self._timer_handle.stop()
            self._timer_handle = None
        content = self.query_one("#viz-content", Static)
        content.update("")

    def _render_bars(self, values: list[float]) -> str:
        """将频谱数据渲染为竖向填满的 ASCII 条形图."""
        chars = " ▁▂▃▄▅▆▇█"
        if not values or max(values) <= 0:
            return ""
        # 归一化到 0–8
        max_val = max(values)
        normalized = [min(8, int(v / max_val * 8)) for v in values]
        # 渲染多行（从上到下），填满高度
        lines = []
        for level in range(8, 0, -1):
            row = ""
            for v in normalized:
                if v >= level:
                    row += chars[level] * 2
                else:
                    row += "  "
            lines.append(row)
        return "\n".join(lines)

    def _update_bars(self) -> None:
        """从数据源获取频谱并更新显示."""
        if self._get_spectrum is not None:
            try:
                values = self._get_spectrum()
            except Exception:
                values = [0.0] * self._bars
        else:
            values = [0.0] * self._bars
        content = self.query_one("#viz-content", Static)
        content.update(self._render_bars(values))

    def set_active(self, active: bool) -> None:
        """设置为活跃/非活跃状态."""
        if active:
            self.start()
        else:
            self.stop()


class CommandInput(Container):
    """命令行输入区域 — 提示标签 + 输入框."""

    def compose(self) -> ComposeResult:
        yield Label("命令行，可以让 AI 解说歌曲和寻找相似歌曲", id="cmd-hint")
        yield Input(
            placeholder="输入命令 (help 查看可用命令)...",
            id="cmd-input",
        )

    def on_mount(self) -> None:
        self.styles.height = "auto"
        hint = self.query_one("#cmd-hint", Label)
        hint.styles.text_style = "dim"
        hint.styles.content_align_horizontal = "left"
        cmd = self.query_one("#cmd-input", Input)
        cmd.styles.width = "100%"

    def get_value(self) -> str:
        return self.query_one("#cmd-input", Input).value

    def clear(self) -> None:
        self.query_one("#cmd-input", Input).value = ""
