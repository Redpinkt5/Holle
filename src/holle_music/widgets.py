"""Textual custom widgets for Holle Music player.

Widgets:
    NowPlaying   — song info panel with clickable progress bar.
    PlaylistPanel — scrollable song list panel.
    Controls     — playback control buttons.
    Visualizer   — 24-band real-time ASCII spectrum bars.
    CommandInput — command line input area with hint label.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.message import Message
from textual.widgets import Static, ListView, ListItem, Input, Label, Button, RichLog
from textual.events import MouseDown, MouseMove, MouseUp


def _rotating_color(offset: int = 0) -> str:
    """Return a color from the current palette that rotates over time."""
    import time
    colors = _SHIMMER_PALETTES[_current_palette]
    idx = (int(time.time() * 4) + offset) % len(colors)
    return colors[idx]


class TruncatedStatic(Static):
    """Static that truncates with ellipsis when text overflows container width."""

    def render(self):
        text = self.content
        w = self.size.width
        if w > 0 and isinstance(text, str) and len(text) > w:
            return text[: w - 1] + "…"
        return super().render()


class ProgressBar(Static, can_focus=True):
    """Clickable/draggable progress bar with time display."""

    _position: float = 0.0
    _duration: float = 0.0
    _on_seek: object = None
    _dragging: bool = False
    _shimmer_timer: object = None

    def set_position(self, pos: float, duration: float) -> None:
        self._position = max(0.0, min(1.0, pos)) if duration > 0 else 0.0
        self._duration = duration
        self.refresh()

    def set_on_seek(self, callback) -> None:
        self._on_seek = callback

    def on_mount(self) -> None:
        self._shimmer_timer = self.set_interval(_SHIMMER_INTERVAL, self.refresh)

    def render(self) -> str:
        cur = self._fmt(self._position * self._duration)
        tot = self._fmt(self._duration)
        suffix = f" {cur}/{tot}"
        bar_w = max(10, self.size.width - len(suffix))
        filled = int(self._position * bar_w)
        empty = bar_w - filled
        bar = _gradient_bar(filled, "█") + "─" * empty
        return f"{bar}{suffix}"

    @staticmethod
    def _fmt(s: float) -> str:
        if s <= 0:
            return "0:00"
        m = int(s // 60)
        sec = int(s % 60)
        return f"{m}:{sec:02d}"

    def _ratio(self, x: int) -> float:
        cur = self._fmt(self._position * self._duration)
        tot = self._fmt(self._duration)
        suffix_w = len(f" {cur}/{tot}")
        bar_w = max(10, self.size.width - suffix_w)
        return max(0.0, min(1.0, (x - 0.5) / bar_w))

    def on_mouse_down(self, event: MouseDown) -> None:
        self._dragging = True
        self.capture_mouse()
        if self._duration > 0:
            self._position = self._ratio(event.x)
            self.refresh()
            if self._on_seek:
                self._on_seek(self._position * self._duration)

    def on_mouse_move(self, event: MouseMove) -> None:
        if self._dragging and self._duration > 0:
            self._position = self._ratio(event.x)
            self.refresh()
            if self._on_seek:
                self._on_seek(self._position * self._duration)

    def on_mouse_up(self, event: MouseUp) -> None:
        if self._dragging:
            self._dragging = False
            self.release_mouse()


# ── Shimmer ──────────────────────────────────────────────────────────────

def _gradient_bar(count: int, char: str = "█", offset: int = 0) -> str:
    """Rich markup bar: light → current palette dark color."""
    target = _rotating_color(offset)  # rotating color for colorful effect
    tr, tg, tb = int(target[1:3], 16), int(target[3:5], 16), int(target[5:7], 16)
    parts = []
    for i in range(count):
        t = i / max(1, count - 1)
        r = int(255 - (255 - tr) * t)
        g = int(255 - (255 - tg) * t)
        b = int(255 - (255 - tb) * t)
        parts.append(f"[#{r:02x}{g:02x}{b:02x}]{char}[/]")
    return "".join(parts)


_SHIMMER_PALETTES: dict[str, list[str]] = {
    "pink":     ["#ff69b4", "#ff85c0", "#ff1493", "#ff6eb4", "#ffb6c1",
                 "#ff99cc", "#db7093", "#ff77aa", "#ff4da6", "#ff8da1"],
    "yellow":   ["#ffd700", "#ffec8b", "#ffdb58", "#ffe4b5", "#f0e68c",
                 "#eedd82", "#daa520", "#ffc125", "#fce883", "#fff8dc"],
    "red":      ["#ff4500", "#ff6347", "#dc143c", "#ff0000", "#cd5c5c",
                 "#f08080", "#e9967a", "#fa8072", "#ff6b6b", "#ee2c2c"],
    "blue":     ["#1e90ff", "#00bfff", "#87ceeb", "#4682b4", "#5f9ea0",
                 "#6495ed", "#4169e1", "#0000cd", "#00ced1", "#7ec8e3"],
    "purple":   ["#8b00ff", "#9932cc", "#ba55d3", "#da70d6", "#ee82ee",
                 "#dda0dd", "#ff00ff", "#8b008b", "#9400d3", "#9370db"],
    "green":    ["#00ff7f", "#3cb371", "#2e8b57", "#228b22", "#32cd32",
                 "#7cfc00", "#00fa9a", "#98fb98", "#90ee90", "#adff2f"],
    "orange":   ["#ff8c00", "#ffa500", "#ffb347", "#ffd700", "#ff7f50",
                 "#f4a460", "#d2691e", "#cd853f", "#ff6347", "#e59866"],
    "gray":     ["#b0b0b0", "#c0c0c0", "#d3d3d3", "#a9a9a9", "#808080",
                 "#696969", "#778899", "#e0e0e0", "#f5f5f5", "#bebebe"],
    "brown":    ["#8b4513", "#a0522d", "#d2b48c", "#deb887", "#f5deb3",
                 "#d2691e", "#b8860b", "#cd853f", "#8b7355", "#c4a882"],
    "black":    ["#333333", "#444444", "#555555", "#666666", "#777777",
                 "#888888", "#999999", "#2c2c2c", "#3d3d3d", "#4e4e4e"],
    "white":    ["#ffffff"],
    "colorful": ["#ff69b4", "#ffd700", "#ff4500", "#1e90ff", "#8b00ff",
                 "#00ff7f", "#ff8c00", "#b0b0b0", "#8b4513", "#ffffff"],
}
_current_palette: str = "pink"
_SHIMMER_SPARKLES = ["♠︎" , "♥︎","♦︎", "♣︎","♚",
                     "♛", "♜", "♝", "♞"
                     ,"♪", "♫", "♬", "♭",
                     "♮", "𝄞" , "𝄡" ,"𝄫","𓏢"]
_SHIMMER_INTERVAL = 0.24


def set_shimmer_palette(name: str) -> bool:
    """Switch shimmer color palette. Returns True if valid name."""
    global _current_palette
    if name in _SHIMMER_PALETTES:
        _current_palette = name
        return True
    return False


def get_shimmer_palette() -> str:
    return _current_palette


def _start_shimmer(widget: Static, offset: int = 0) -> None:
    """Cycle border color + sparkle prefix with per-widget offset."""
    if getattr(widget, "_shimmer_timer", None) is not None:
        return
    base_title: str = getattr(widget, "_shimmer_base_title", widget.BORDER_TITLE)
    idx = [0]

    def _tick():
        colors = _SHIMMER_PALETTES[_current_palette]
        i = (idx[0] + offset) % len(colors)
        color = colors[i]
        sparkle = _SHIMMER_SPARKLES[idx[0] % len(_SHIMMER_SPARKLES)]
        widget.border_title = f"{sparkle} {base_title}"
        widget.styles.border = ("solid", color)
        idx[0] += 1

    widget._shimmer_timer = widget.set_interval(_SHIMMER_INTERVAL, _tick)


def _stop_shimmer(widget: Static) -> None:
    """Stop shimmer and reset border to static white."""
    timer = getattr(widget, "_shimmer_timer", None)
    if timer is not None:
        try:
            timer.stop()
        except Exception:
            pass
        widget._shimmer_timer = None
    base_title: str = getattr(widget, "_shimmer_base_title", widget.BORDER_TITLE)
    widget.border_title = f"✻ {base_title}"
    widget.styles.border = ("solid", "white")


def _extract_cover(path: str) -> str:
    """Extract album cover, return Rich markup with half-block pixel art."""
    try:
        from mutagen import File as MutagenFile
        from PIL import Image
        import io
        audio = MutagenFile(path)
        if audio is None:
            return "[dim]♪[/dim]"
        data = None
        # FLAC: pictures attribute
        if hasattr(audio, "pictures") and audio.pictures:
            data = audio.pictures[0].data
        # MP3: ID3 APIC frames
        if not data and hasattr(audio, "tags"):
            for tag in audio.tags.values():
                if getattr(tag, "FrameID", "") == "APIC":
                    data = tag.data
                    break
        if not data:
            return "[dim]♪[/dim]"
        img = Image.open(io.BytesIO(data)).convert("RGB")
        # 25 cols x 13 rows = 25x26 pixels with half-blocks (square in terminal)
        w, h = 25, 26
        img = img.resize((w, h))
        lines = []
        for y in range(0, h, 2):
            parts = []
            for x in range(w):
                r1, g1, b1 = img.getpixel((x, y))
                r2, g2, b2 = img.getpixel((x, y + 1)) if y + 1 < h else (0, 0, 0)
                c1 = f"#{r1:02x}{g1:02x}{b1:02x}"
                c2 = f"#{r2:02x}{g2:02x}{b2:02x}"
                parts.append(f"[{c1} on {c2}]▀[/]")
            lines.append("".join(parts))
        return "\n".join(lines)
    except Exception as e:
        return f"[dim]♪ err:{e}[/dim]"


# ── NowPlaying ───────────────────────────────────────────────────────────

class NowPlaying(Static):
    """Song info panel with progress bar and AI-generated background."""

    BORDER_TITLE = "✻ Listening"

    _song_info: str = ""
    _song_info_loading: bool = False
    _shimmer_timer: object = None
    _shimmer_base_title: str = "Listening"

    def start_shimmer(self) -> None:
        _start_shimmer(self)

    def stop_shimmer(self) -> None:
        _stop_shimmer(self)

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static("", id="np-cover")
            with Vertical(id="np-right"):
                with Vertical(id="np-info"):
                    with Horizontal(id="np-header"):
                        yield Static("", id="np-title")
                        yield TruncatedStatic("", id="np-artist")
                    yield Static("", id="np-album")
                with VerticalScroll(id="np-song-info"):
                    yield Static("", id="np-song-info-text")
        yield ProgressBar(id="np-progress")

    def on_mount(self) -> None:
        self.styles.border = ("solid", "white")
        self.styles.padding = (0, 1)
        self.styles.overflow_y = "auto"
        cover = self.query_one("#np-cover", Static)
        cover.styles.width = 25
        cover.styles.min_width = 25
        cover.styles.height = 13
        cover.styles.content_align = ("center", "middle")
        cover.styles.margin = (0, 1, 0, 0)
        right = self.query_one("#np-right", Vertical)
        right.styles.width = "1fr"
        info = self.query_one("#np-info", Vertical)
        info.styles.height = "auto"
        header = self.query_one("#np-header", Horizontal)
        header.styles.height = "auto"
        title = self.query_one("#np-title", Static)
        title.styles.content_align = ("left", "middle")
        title.styles.width = "auto"
        title.styles.margin = (0, 2, 0, 0)
        artist = self.query_one("#np-artist", Static)
        artist.styles.content_align = ("left", "middle")
        artist.styles.width = "1fr"
        album = self.query_one("#np-album", Static)
        album.styles.content_align = ("left", "middle")
        album.styles.width = "100%"
        song_info = self.query_one("#np-song-info", VerticalScroll)
        song_info.styles.width = "100%"
        song_info.styles.height = "1fr"
        self.query_one("#np-progress", ProgressBar).styles.margin = (0, 0, 0, 0)

    def set_song(self, song) -> None:
        self._song_info = ""
        self._song_info_loading = False
        if song is None:
            self.query_one("#np-cover", Static).update("[dim]♪[/dim]")
            self.query_one("#np-title", Static).update("[dim]No Song[/dim]")
            self.query_one("#np-artist", Static).update("")
            self.query_one("#np-album", Static).update("")
            self.query_one("#np-song-info-text", Static).update("")
            return
        self.query_one("#np-title", Static).update(song.title)
        self.query_one("#np-artist", Static).update(song.artist)
        self.query_one("#np-album", Static).update(f"[dim]{song.album}[/dim]")
        self.query_one("#np-song-info-text", Static).update("[dim]正在获取歌曲背景...[/dim]")
        self._song_info_loading = True
        art = _extract_cover(str(song.path))
        self.query_one("#np-cover", Static).update(art)

    def set_song_info(self, text: str) -> None:
        self._song_info = text
        self._song_info_loading = False
        self.query_one("#np-song-info-text", Static).update(text)

    def set_song_info_error(self, msg: str) -> None:
        self._song_info_loading = False
        self.query_one("#np-song-info-text", Static).update(f"[dim]{msg}[/dim]")

    @property
    def progress(self) -> ProgressBar:
        return self.query_one("#np-progress", ProgressBar)


# ── Chat Bubbles ──────────────────────────────────────────────────────


class ChatBubbles(RichLog, can_focus=True):
    """WeChat-style chat: user right, AI left, native scrolling."""

    BORDER_TITLE = "Chat"
    _messages: list[tuple[str, str, str]] = []  # [(role, text, time), ...]
    _shimmer_timer: object = None

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("highlight", False)
        kwargs.setdefault("markup", True)
        kwargs.setdefault("wrap", True)
        super().__init__(*args, **kwargs)

    def on_mount(self) -> None:
        super().on_mount()
        # Chat bubbles use a fixed palette color; no shimmer timer.

    def add_user_msg(self, text: str) -> None:
        from datetime import datetime
        t = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._messages.append(("user", text, t))
        self._redraw()

    _PENDING_TEXT = [
        "沉思中", "推敲中", "琢磨中", "斟酌中", "思量中", "思忖中",
        "思索中", "冥思苦想中", "若有所思中", "胡思乱想中", "深思熟虑中",
        "百思准备得其解中", "多谋善虑中", "好谋善断中", "集思广益中",
        "困心衡虑中", "殚精竭虑中", "咬文嚼字中", "口诵心惟中", "迁思回虑中",
        "字斟句酌中", "熟思审处中", "蛐蛐中", "霞思云想中", "霞思天想中",
        "想入非非中", "心存目想中", "异想天开中", "详思中", "锐虑中",
        "睿虑中", "研思中", "动手动脚中",
    ]

    def set_pending(self) -> None:
        import random
        t = random.choice(self._PENDING_TEXT)
        self._messages.append(("pending", t, ""))
        self._redraw()

    def add_ai_msg(self, text: str) -> None:
        from datetime import datetime
        t = datetime.now().strftime("%Y-%m-%d %H:%M")
        if self._messages and self._messages[-1][0] == "pending":
            self._messages.pop()
        self._messages.append(("ai", text, t))
        self._redraw()

    def _redraw(self) -> None:
        self.clear()
        from rich.cells import cell_len
        try:
            w = self.size.width
        except Exception:
            w = 40
        if w < 20:
            w = 40
        ai_color = _SHIMMER_PALETTES.get(get_shimmer_palette(), _SHIMMER_PALETTES["pink"])[0]
        max_w = max(20, w - 6)
        ts_color = "dim"
        for role, text, t in self._messages:
            if role == "user":
                self.write(f"[{ts_color}]{' ' * (w - len(t) - 2)}{t}[/]")
                line = text.replace("\n", " ")
                cw = cell_len(line)
                pad = max(0, w - cw - 2)
                self.write(f"{' ' * pad}[on #333333]{line}[/]")
            elif role == "pending":
                self.write(f" [{ts_color}]{text}[/]")
            else:
                self.write(f"[{ts_color}]{t}[/]")
                for line in self._wrap_text(text, max_w):
                    self.write(f" [black on {ai_color}]{line}[/] ")
            self.write("")

    @staticmethod
    def _wrap_text(text: str, max_w: int) -> list[str]:
        from rich.cells import cell_len
        result: list[str] = []
        current = ""
        for ch in text:
            if ch == "\n":
                if current:
                    result.append(current)
                current = ""
            elif cell_len(current + ch) <= max_w:
                current += ch
            else:
                if current:
                    result.append(current)
                current = ch
        if current:
            result.append(current)
        return result if result else [""]


# ── Equalizer ──────────────────────────────────────────────────────────


class Equalizer(Static, can_focus=True):
    """Vertical EQ sliders: 8 bands from low to high frequency."""

    BORDER_TITLE = "EQ"

    _bands: int = 8
    _values: list[float]  # 0.0 - 1.0 per band
    _dragging: int = -1
    _config_path = None
    _shimmer_timer: object = None

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._values = [0.5] * self._bands

    def on_mount(self) -> None:
        self.styles.border = ("solid", "white")
        self._load()
        self._shimmer_timer = self.set_interval(_SHIMMER_INTERVAL, self.refresh)

    def _config_file(self):
        from pathlib import Path
        return Path(__file__).parent / ".holle_eq.json"

    def _load(self) -> None:
        import json
        try:
            cfg = self._config_file()
            if cfg.exists():
                data = json.loads(cfg.read_text())
                saved = data.get("eq", [0.5] * self._bands)
                self._values = saved[:self._bands]
        except Exception:
            pass

    def _save(self) -> None:
        import json
        try:
            cfg = self._config_file()
            cfg.write_text(json.dumps({"eq": self._values}))
        except Exception:
            pass

    def render(self) -> str:
        try:
            h = max(4, self.size.height - 2)
        except Exception:
            h = 10
        try:
            bar_w = max(2, (self.size.width - self._bands) // self._bands)
        except Exception:
            bar_w = 3
        if bar_w < 1:
            bar_w = 1
        guides = {0, h // 4, h // 2, h * 3 // 4, h - 1}
        lines = []
        for level in range(h - 1, -1, -1):
            is_guide = level in guides
            fill_char = "█"
            empty_char = "┅" if is_guide else " "
            row = ""
            for v in self._values:
                filled_lines = int(v * h)
                for _ in range(bar_w):
                    row += fill_char if filled_lines > level else empty_char
                row += " "
            lines.append(row)
        try:
            total_w = len(lines[0]) if lines else 20
            labels = "L" + " " * (total_w - 2) + "H"
        except Exception:
            labels = "L" + " " * 18 + "H"
        lines.append(labels)
        return "\n".join(lines)

    def _band_at(self, x: int) -> int:
        try:
            bar_w = max(2, (self.size.width - self._bands) // self._bands)
        except Exception:
            bar_w = 3
        band = x // (bar_w + 1)
        return band if 0 <= band < self._bands else -1

    def _value_at(self, y: int) -> float:
        try:
            h = self.size.height - 2
        except Exception:
            h = 10
        if h < 1:
            h = 1
        return 1.0 - (y / h)

    def on_mouse_down(self, event) -> None:
        band = self._band_at(event.x)
        if band >= 0:
            self._dragging = band
            self.capture_mouse()
            self._values[band] = max(0.0, min(1.0, self._value_at(event.y)))
            self.refresh()

    def on_mouse_move(self, event) -> None:
        if self._dragging >= 0:
            self._values[self._dragging] = max(0.0, min(1.0, self._value_at(event.y)))
            self.refresh()

    def on_mouse_up(self, event) -> None:
        if self._dragging >= 0:
            self._values[self._dragging] = max(0.0, min(1.0, self._value_at(event.y)))
            self._dragging = -1
            self.release_mouse()
            self._save()


# ── Playlist panel ─────────────────────────────────────────────────────


class PlaylistPanel(Static):
    """Scrollable song list with white border."""

    BORDER_TITLE = "播放列表"

    @staticmethod
    def _pad_disp(s: str, target_w: int) -> str:
        from rich.cells import cell_len
        dw = cell_len(s)
        if dw <= target_w:
            return s + " " * (target_w - dw)
        limit = target_w - 2
        trimmed = ""
        for ch in s:
            if cell_len(trimmed + ch) > limit:
                break
            trimmed += ch
        return trimmed + "…"

    def compose(self) -> ComposeResult:
        yield Static("暂无歌曲", id="playlist-placeholder")
        yield ListView(id="playlist-list")

    def on_mount(self) -> None:
        self.styles.border = ("solid", "white")
        self._hide_placeholder(False)

    def _hide_placeholder(self, hidden: bool) -> None:
        self.query_one("#playlist-placeholder", Static).display = False if hidden else True
        self.query_one("#playlist-list", ListView).display = True if hidden else False

    def load_songs(self, songs: list) -> None:
        from rich.cells import cell_len
        lst = self.query_one("#playlist-list", ListView)
        lst.clear()
        if not songs:
            self._hide_placeholder(False)
            return
        self._hide_placeholder(True)
        max_dw = max((cell_len(s.title) for s in songs), default=20)
        title_w = min(max_dw + 2, 40)
        for song in songs:
            padded = self._pad_disp(song.title, title_w)
            label = f"{padded}  {song.artist}"
            lst.append(ListItem(Static(label)))

    def get_selected_index(self) -> int | None:
        lst = self.query_one("#playlist-list", ListView)
        return lst.index if lst.index is not None else None


# ── Mascot ──────────────────────────────────────────────────────────────


class Mascot(Static):
    """Pixel-art mascot with mouse-tracking eyes.

    Click zones: left third = prev, center = play/pause, right third = next.
    """

    BORDER_TITLE = ""
    COLS: int = 14
    ROWS: int = 7

    _BODY: list[str] = [
        "......██......",
        "....██████....",
        "..██████████..",
        "██████████████",
        "..██████████..",
        "....██████....",
        "......██......",
    ]

    _EYES: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {
        "center":        ((3, 5), (3, 8)),
        "up":            ((2, 5), (2, 8)),
        "down":          ((4, 5), (4, 8)),
        "left":          ((3, 3), (3, 6)),
        "right":         ((3, 7), (3, 10)),
        "top_left":      ((2, 4), (2, 7)),
        "top_right":     ((2, 6), (2, 9)),
        "bottom_left":   ((4, 4), (4, 7)),
        "bottom_right":  ((4, 6), (4, 9)),
    }

    class Clicked(Message):
        def __init__(self, zone: str) -> None:
            super().__init__()
            self.zone = zone

    _direction: str = "center"
    _active: bool = False
    _shimmer_timer: object = None
    _shimmer_idx: int = 0

    def on_mount(self) -> None:
        self.styles.width = self.COLS
        self.styles.height = self.ROWS

    def update_mouse(self, screen_x: int, screen_y: int) -> None:
        new_dir = self._calc_direction(screen_x, screen_y)
        if new_dir != self._direction:
            self._direction = new_dir
            self.refresh()

    def set_active(self, active: bool) -> None:
        if active != self._active:
            self._active = active
            if active:
                self._start_shimmer(offset=8)
            else:
                self._stop_shimmer()

    def _start_shimmer(self, offset: int = 0) -> None:
        if self._shimmer_timer is not None:
            return
        idx = [0]

        def _tick():
            colors = _SHIMMER_PALETTES[_current_palette]
            self.styles.color = colors[(idx[0] + offset) % len(colors)]
            idx[0] += 1

        self._shimmer_timer = self.set_interval(_SHIMMER_INTERVAL, _tick)

    def _stop_shimmer(self) -> None:
        if self._shimmer_timer is not None:
            try:
                self._shimmer_timer.stop()
            except Exception:
                pass
            self._shimmer_timer = None
        self.styles.color = "#ffffff"

    def _calc_direction(self, sx: int, sy: int) -> str:
        import math
        cx = self.region.x + self.region.width / 2
        cy = self.region.y + self.region.height / 2
        dx = sx - cx
        dy = sy - cy
        if math.hypot(dx, dy) < 5:
            return "center"
        angle = math.degrees(math.atan2(dy, dx))
        if -22.5 <= angle < 22.5:
            return "right"
        elif 22.5 <= angle < 67.5:
            return "bottom_right"
        elif 67.5 <= angle < 112.5:
            return "down"
        elif 112.5 <= angle < 157.5:
            return "bottom_left"
        elif angle >= 157.5 or angle < -157.5:
            return "left"
        elif -157.5 <= angle < -112.5:
            return "top_left"
        elif -112.5 <= angle < -67.5:
            return "up"
        else:
            return "top_right"

    def render(self) -> str:
        """Plain-text render, color via CSS."""
        grid = [[0] * self.COLS for _ in range(self.ROWS)]
        for r, row_str in enumerate(self._BODY):
            for c, ch in enumerate(row_str):
                if ch == "█":
                    grid[r][c] = 1
        (lr, lc), (rr, rc) = self._EYES[self._direction]
        for er, ec in ((lr, lc), (rr, rc)):
            if 0 <= er < self.ROWS and 0 <= ec < self.COLS:
                grid[er][ec] = 2
        lines = []
        for row in grid:
            chars = []
            for cell in row:
                if cell == 1:
                    chars.append("█")
                else:
                    chars.append(" ")
            lines.append("".join(chars))
        return "\n".join(lines)

    def on_click(self, event) -> None:
        w = self.size.width
        h = self.size.height
        if w <= 0 or h <= 0:
            return
        nx = event.x / w
        ny = event.y / h
        # Top-center area cycles play mode, matching the desktop pet.
        if ny < 0.3 and 0.25 <= nx <= 0.75:
            self.post_message(self.Clicked("mode"))
            return
        if nx < 0.33:
            self.post_message(self.Clicked("prev"))
        elif nx < 0.66:
            self.post_message(self.Clicked("toggle"))
        else:
            self.post_message(self.Clicked("next"))


# ── Controls ──────────────────────────────────────────────────────────


class Controls(Static):
    """Playback controls: prev, mascot, next + play mode + clock."""

    BORDER_TITLE = ""

    class PrevNext(Message):
        def __init__(self, action: str) -> None:
            super().__init__()
            self.action = action

    class ModeChange(Message):
        def __init__(self, mode: str) -> None:
            super().__init__()
            self.mode = mode  # "sequential", "repeat", "random"

    class PetLaunch(Message):
        """Request to launch the desktop pet window."""

        pass

    _PREV = "\n\n\n█\n"
    _NEXT = "\n\n\n█\n"
    _mode: str = "sequential"
    _shimmer_timer: object = None

    def compose(self) -> ComposeResult:
        with Vertical(id="controls-row"):
            with Horizontal(id="controls-top"):
                yield Mascot(id="mascot")
                yield Static("", id="clock")
                yield Button(" ◆ ", id="btn-pet", classes="mode-btn")
            with Horizontal(id="controls-modes"):
                yield Button(" ⭢ ", id="btn-mode-seq", classes="mode-btn")
                yield Button(" ↬ ", id="btn-mode-rand", classes="mode-btn")
                yield Button(" ⟳ ", id="btn-mode-one", classes="mode-btn")
        yield ChatBubbles(id="chat-bubbles")

    def on_mount(self) -> None:
        self.styles.content_align = ("center", "middle")
        self._update_mode_buttons()
        self._shimmer_timer = self.set_interval(_SHIMMER_INTERVAL, self._update_mode_buttons)
        def _update_clock():
            from datetime import datetime
            now = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
            try:
                self.query_one("#clock", Static).update(f"[dim]{now}  V0.1.1[/dim]")
            except Exception:
                pass
        _update_clock()
        self.set_interval(1.0, _update_clock)

    def _update_mode_buttons(self) -> None:
        """Highlight active play mode button with rotating shimmer color."""
        active_color = _rotating_color()
        for mid, active in [
            ("btn-mode-seq", self._mode == "sequential"),
            ("btn-mode-one", self._mode == "repeat"),
            ("btn-mode-rand", self._mode == "random"),
        ]:
            try:
                btn = self.query_one(f"#{mid}", Button)
                if active:
                    btn.add_class("active-mode")
                    btn.styles.color = active_color
                else:
                    btn.remove_class("active-mode")
                    btn.styles.color = "#888888"
            except Exception:
                pass

    def set_mode(self, mode: str) -> None:
        """Set the displayed mode without posting a change message."""
        if mode in ("sequential", "random", "repeat"):
            self._mode = mode
            self._update_mode_buttons()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-prev":
            self.post_message(self.PrevNext("prev"))
        elif bid == "btn-next":
            self.post_message(self.PrevNext("next"))
        elif bid == "btn-pet":
            self.post_message(self.PetLaunch())
        elif bid == "btn-mode-seq":
            self._mode = "sequential"
            self._update_mode_buttons()
            self.post_message(self.ModeChange("sequential"))
        elif bid == "btn-mode-one":
            self._mode = "repeat"
            self._update_mode_buttons()
            self.post_message(self.ModeChange("repeat"))
        elif bid == "btn-mode-rand":
            self._mode = "random"
            self._update_mode_buttons()
            self.post_message(self.ModeChange("random"))

    def set_active(self, active: bool) -> None:
        self.query_one("#mascot", Mascot).set_active(active)

    def update_mouse(self, screen_x: int, screen_y: int) -> None:
        self.query_one("#mascot", Mascot).update_mouse(screen_x, screen_y)


# ── Visualizer ─────────────────────────────────────────────────────────


class VolumeBar(Static, can_focus=True):
    """Clickable/draggable volume control bar."""

    _volume: float = 1.0
    _on_change: object = None
    _dragging: bool = False
    _shimmer_timer: object = None

    def on_mount(self) -> None:
        self._shimmer_timer = self.set_interval(_SHIMMER_INTERVAL, self.refresh)

    def set_volume(self, vol: float) -> None:
        self._volume = max(0.0, min(1.0, vol))
        self.refresh()

    def set_on_change(self, callback) -> None:
        self._on_change = callback

    def render(self) -> str:
        prefix = "Volume "
        suffix = f" {int(self._volume * 100)}%"
        bar_w = max(8, self.size.width - len(prefix) - len(suffix) - 4)
        filled = int(self._volume * bar_w)
        empty = bar_w - filled
        bar = _gradient_bar(filled, "█", offset=5) + "─" * empty
        return f"{prefix}{bar}{suffix}"

    def _ratio(self, x: int) -> float:
        prefix = "Volume "
        suffix = f" {int(self._volume * 100)}%"
        bar_w = max(8, self.size.width - len(prefix) - len(suffix) - 4)
        offset = len(prefix) + 1
        return max(0.0, min(1.0, (x - offset) / bar_w))

    def on_mouse_down(self, event: MouseDown) -> None:
        self._dragging = True
        self.capture_mouse()
        self._volume = self._ratio(event.x)
        self.refresh()
        if self._on_change:
            self._on_change(self._volume)

    def on_mouse_move(self, event: MouseMove) -> None:
        if self._dragging:
            self._volume = self._ratio(event.x)
            self.refresh()
            if self._on_change:
                self._on_change(self._volume)

    def on_mouse_up(self, event: MouseUp) -> None:
        if self._dragging:
            self._dragging = False
            self.release_mouse()


class Visualizer(Static):
    """Real-time 24-band ASCII spectrum with volume bar."""

    BORDER_TITLE = "✻ Audio Spectrum Bars"

    _bars: int = 24
    _timer: object | None = None
    _watchdog: object | None = None
    _get_spectrum: object = None
    _frame_count: int = 0
    _last_seen: int = -1
    _shimmer_timer: object = None
    _shimmer_base_title: str = "Audio Spectrum Bars"

    _active: bool = False
    _decaying: bool = False
    _display: list[float] = []
    _smooth: float = 0.35

    DECAY: float = 0.88
    DECAY_CUTOFF: float = 0.015

    def start_shimmer(self) -> None:
        _start_shimmer(self, offset=4)

    def stop_shimmer(self) -> None:
        _stop_shimmer(self)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("", id="viz-content")
            yield VolumeBar(id="viz-volume")

    def on_mount(self) -> None:
        self.styles.border = ("solid", "white")
        self.styles.padding = (0, 1)
        content = self.query_one("#viz-content", Static)
        content.styles.height = "1fr"
        vol = self.query_one("#viz-volume", VolumeBar)
        vol.styles.height = "auto"

    @property
    def volume_bar(self) -> VolumeBar:
        return self.query_one("#viz-volume", VolumeBar)

    def set_spectrum_source(self, source) -> None:
        self._get_spectrum = source

    def _ensure_timer(self) -> None:
        if self._timer is None:
            self._frame_count = 0
            self._last_seen = -1
            self._timer = self.set_interval(1 / 30, self._tick)
            self._watchdog = self.set_interval(2.0, self._watchdog_check)

    def start(self) -> None:
        self._active = True
        self._decaying = False
        self._ensure_timer()

    def stop(self) -> None:
        self._active = False
        if not self._display:
            self._display = [0.0] * self._bars
        self._decaying = True
        self._ensure_timer()

    def _watchdog_check(self) -> None:
        if self._frame_count == self._last_seen and self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
            self._timer = self.set_interval(1 / 30, self._tick)
        self._last_seen = self._frame_count

    def _tick(self) -> None:
        import math
        try:
            src = self._get_spectrum
            raw = src() if src is not None else [0.0] * self._bars
            raw = [max(0.0, 0.0 if math.isnan(v) else v) for v in raw]
        except Exception:
            raw = [0.0] * self._bars
        try:
            if self._active:
                if len(self._display) != len(raw):
                    self._display = list(raw)
                else:
                    for i in range(len(raw)):
                        self._display[i] += (raw[i] - self._display[i]) * self._smooth
            elif self._decaying:
                all_low = True
                for i in range(len(self._display)):
                    self._display[i] *= self.DECAY
                    if self._display[i] > self.DECAY_CUTOFF:
                        all_low = False
                if all_low:
                    self._display = [0.0] * self._bars
                    self._decaying = False
            else:
                self._display = [0.0] * self._bars
            self.query_one("#viz-content", Static).update(
                self._render_bars(self._display)
            )
            self._frame_count += 1
        except Exception:
            pass

    def _palette_gradient(self, t: float) -> str:
        """Gradient from white to current shimmer palette color."""
        hex_color = _rotating_color()
        tr = int(hex_color[1:3], 16)
        tg = int(hex_color[3:5], 16)
        tb = int(hex_color[5:7], 16)
        r = 255 - int((255 - tr) * t)
        g = 255 - int((255 - tg) * t)
        b = 255 - int((255 - tb) * t)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _render_bars(self, values: list[float]) -> str:
        import math
        if not values:
            return ""
        clean = [v for v in values if not math.isnan(v)]
        if not clean:
            return ""
        avail_w = max(1, self.size.width - 2)
        avail_h = max(1, self.size.height - 2)
        max_h = max(1, int(avail_h * 0.9))
        bar_count = (avail_w + 1) // 2
        if bar_count < 2:
            return ""
        n_spec = len(values)
        step_spec = (n_spec - 1) / (bar_count - 1) if bar_count > 1 else 0.0
        bar_values = []
        for i in range(bar_count):
            src = i * step_spec
            lo = int(src)
            hi = min(lo + 1, n_spec - 1)
            frac = src - lo
            bar_values.append(values[lo] * (1.0 - frac) + values[hi] * frac)
        bar_step = (avail_w - 1) / (bar_count - 1) if bar_count > 1 else 0.0
        bar_colors: list[str] = []
        for i in range(bar_count):
            t = i / (bar_count - 1) if bar_count > 1 else 0
            bar_colors.append(self._palette_gradient(t))
        lines = []
        for level in range(max_h, 0, -1):
            row = [" "] * avail_w
            row_color: list[str | None] = [None] * avail_w
            for i in range(bar_count):
                x = round(i * bar_step)
                v = bar_values[i]
                bar_h = int((0.0 if math.isnan(v) else v) * max_h)
                if bar_h >= level and 0 <= x < avail_w:
                    row[x] = "█"
                    row_color[x] = bar_colors[i]
            parts: list[str] = []
            i = 0
            while i < avail_w:
                c = row_color[i]
                j = i
                while j < avail_w and row_color[j] == c:
                    j += 1
                seg = "".join(row[i:j])
                if c:
                    parts.append(f"[{c}]{seg}[/]")
                else:
                    parts.append(seg)
                i = j
            lines.append("".join(parts))
        if avail_h - max_h >= 2:
            tick_defs = [
                (0, "1Hz"),
                (round(avail_w * 0.25), "500Hz"),
                (round(avail_w * 0.5), "2kHz"),
                (round(avail_w * 0.75), "8kHz"),
                (avail_w - 1, "20kHz"),
            ]
            tick_row = [" "] * avail_w
            for tx, _ in tick_defs:
                if 0 <= tx < avail_w:
                    tick_row[tx] = "|"
            lines.append("".join(tick_row))
            label_row = [" "] * avail_w
            for i, (tx, label) in enumerate(tick_defs):
                if i == 0:
                    start = 0
                elif i == len(tick_defs) - 1:
                    start = avail_w - len(label)
                else:
                    start = tx - len(label) // 2
                for j, ch in enumerate(label):
                    idx = start + j
                    if 0 <= idx < avail_w:
                        label_row[idx] = ch
            lines.append("".join(label_row))
        return "\n".join(lines)

    def on_resize(self) -> None:
        try:
            vals = self._display if self._display else [0.0] * self._bars
            self.query_one("#viz-content", Static).update(self._render_bars(vals))
        except Exception:
            pass

    def set_active(self, active: bool) -> None:
        if active:
            self.start()
        else:
            self.stop()


# ── Command input ──────────────────────────────────────────────────────


class CommandInput(Static):
    """Terminal-style command bar: prefix label + input field."""

    BORDER_TITLE = "CLI"
    BINDINGS = [
        Binding("up", "history_up", "", show=False),
        Binding("down", "history_down", "", show=False),
    ]

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    _prompt: str = "E:\\Music>"
    _history: list[str] = []
    _history_idx: int = -1
    _saved_input: str = ""

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static("", id="cmd-prefix")
            yield Input(
                placeholder="输入命令...",
                id="cmd-input",
            )
            yield Static("  /help 帮助", id="cmd-help-hint")

    def on_mount(self) -> None:
        self._update_prefix_display()
        inp = self.query_one("#cmd-input", Input)
        inp.styles.width = "1fr"
        inp.styles.padding = (0, 0)
        inp.styles.content_align = ("left", "middle")
        hint = self.query_one("#cmd-help-hint", Static)
        hint.styles.width = "auto"
        hint.styles.content_align = ("left", "middle")
        hint.styles.text_style = "dim"
        self.call_after_refresh(lambda: inp.focus())

    def on_click(self, event) -> None:
        self.query_one("#cmd-input", Input).focus()

    def _update_prefix_display(self) -> None:
        self.query_one("#cmd-prefix", Static).update(f"[white]{self._prompt} [/white]")

    def set_prefix(self, path: str) -> None:
        self._prompt = f"{path}>"
        if self.is_mounted:
            self._update_prefix_display()

    def push_history(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        if self._history and self._history[-1] == text:
            return
        self._history.append(text)
        self._history_idx = -1
        self._saved_input = ""

    def clear(self) -> None:
        inp = self.query_one("#cmd-input", Input)
        inp.value = ""
        inp.cursor_position = 0

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "cmd-input":
            return
        text = event.value.strip()
        event.input.value = ""
        event.input.cursor_position = 0
        if text:
            self.push_history(text)
            self.post_message(self.Submitted(text))
        event.stop()

    def _navigate_history(self, direction: int) -> None:
        inp = self.query_one("#cmd-input", Input)
        if not self._history:
            return
        if direction > 0:
            if self._history_idx == -1:
                self._saved_input = inp.value
                self._history_idx = 0
            elif self._history_idx < len(self._history) - 1:
                self._history_idx += 1
            inp.value = self._history[-(self._history_idx + 1)]
        else:
            if self._history_idx <= 0:
                self._history_idx = -1
                inp.value = self._saved_input
            else:
                self._history_idx -= 1
                inp.value = self._history[-(self._history_idx + 1)]
        inp.cursor_position = len(inp.value)

    def action_history_up(self) -> None:
        self._navigate_history(1)

    def action_history_down(self) -> None:
        self._navigate_history(-1)
