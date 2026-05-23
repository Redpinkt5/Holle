"""Holle Music — Textual TUI 主应用."""

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Button, Input, ListView
from textual.containers import Grid

from holle_music.models import Song, Playlist
from holle_music.scanner import Scanner
from holle_music.player import Player, PlayerState
from holle_music.widgets import (
    AlbumCover,
    LyricsPanel,
    PlaylistPanel,
    Controls,
    Visualizer,
    CommandInput,
)


class CommandType(Enum):
    NONE = auto()
    PLAY = auto()
    PAUSE = auto()
    STOP = auto()
    NEXT = auto()
    PREVIOUS = auto()
    VOLUME = auto()
    SCAN = auto()
    PLAYLIST = auto()
    HELP = auto()
    QUIT = auto()
    UNKNOWN = auto()


@dataclass
class Command:
    type: CommandType
    args: str = ""


COMMAND_MAP: dict[str, CommandType] = {
    "play": CommandType.PLAY,
    "pause": CommandType.PAUSE,
    "stop": CommandType.STOP,
    "resume": CommandType.PLAY,  # resume is equivalent to play
    "next": CommandType.NEXT,
    "prev": CommandType.PREVIOUS,
    "previous": CommandType.PREVIOUS,
    "volume": CommandType.VOLUME,
    "vol": CommandType.VOLUME,
    "scan": CommandType.SCAN,
    "playlist": CommandType.PLAYLIST,
    "help": CommandType.HELP,
    "?": CommandType.HELP,
    "quit": CommandType.QUIT,
    "exit": CommandType.QUIT,
    "q": CommandType.QUIT,
}


def parse_command(text: str) -> Command:
    """解析用户输入的命令字符串."""
    text = text.strip()
    if not text:
        return Command(CommandType.NONE)

    parts = text.split(maxsplit=1)
    keyword = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    cmd_type = COMMAND_MAP.get(keyword, CommandType.UNKNOWN)
    return Command(cmd_type, args)


class HolleMusicApp(App):
    """Holle Music 主应用."""

    CSS = """
    Grid {
        grid-size: 3 3;
        grid-rows: 45fr 45fr 10fr;
        grid-columns: 1fr 1fr 1fr;
        border: solid white;
        background: black;
    }

    AlbumCover {
        border: solid white;
        height: 100%;
    }

    LyricsPanel {
        border: solid white;
        height: 100%;
    }

    PlaylistPanel {
        border: solid white;
        height: 100%;
        column-span: 1;
        row-span: 2;
    }

    Controls {
        height: 100%;
    }

    Visualizer {
        border: solid white;
        height: 100%;
    }

    CommandInput {
        column-span: 3;
        height: 100%;
    }

    Button {
        background: black;
        color: white;
        min-width: 14;
    }

    Button:focus {
        text-style: bold reverse;
    }

    ListView {
        background: black;
        color: white;
    }

    ListView > ListItem {
        background: black;
        color: white;
    }

    ListView > ListItem.--highlight {
        background: white;
        color: black;
    }

    Input {
        background: black;
        color: white;
        border: solid white;
    }

    Label {
        background: black;
        color: white;
    }

    Static {
        background: black;
        color: white;
    }

    Header {
        background: black;
        color: white;
    }

    Footer {
        background: black;
        color: white;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_play_pause", "播放/暂停"),
        Binding("left", "previous_track", "上一曲"),
        Binding("right", "next_track", "下一曲"),
        Binding("tab", "focus_next", "切换焦点"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.player = Player()
        self.scanner = Scanner()
        self._playlists: dict[str, Playlist] = {}
        self.player.on_song_change(self._on_song_changed)

    def compose(self) -> ComposeResult:
        yield Header()
        with Grid():
            yield AlbumCover(id="album-cover")
            yield LyricsPanel(id="lyrics-panel")
            yield PlaylistPanel(id="playlist-panel")
            yield Controls(id="controls")
            yield Visualizer(id="visualizer")
            yield CommandInput(id="command-input")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Holle Music"
        self.sub_title = "终端音乐播放器"

    def _on_song_changed(self, song: Song | None) -> None:
        if song is not None:
            cover = self.query_one("#album-cover", AlbumCover)
            cover.set_cover_text(f"{song.title}\n\n{song.artist}")
            lyrics = self.query_one("#lyrics-panel", LyricsPanel)
            lyrics.set_lyrics(f"正在播放: {song.title}")

    def action_toggle_play_pause(self) -> None:
        self.player.toggle_play_pause()
        self._update_controls_ui()

    def action_next_track(self) -> None:
        self.player.next()
        self._sync_playlist_selection()

    def action_previous_track(self) -> None:
        self.player.previous()
        self._sync_playlist_selection()

    def _update_controls_ui(self) -> None:
        controls = self.query_one("#controls", Controls)
        controls.set_play_pause_label(self.player.is_playing)
        viz = self.query_one("#visualizer", Visualizer)
        viz.set_active(self.player.is_playing)

    def _sync_playlist_selection(self) -> None:
        playlist = self.query_one("#playlist-panel", PlaylistPanel)
        lst = playlist.query_one("#playlist-list", ListView)
        lst.index = self.player.current_index

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-prev":
            self.action_previous_track()
        elif btn_id == "btn-play-pause":
            self.action_toggle_play_pause()
        elif btn_id == "btn-next":
            self.action_next_track()
        elif btn_id == "btn-song-info":
            song = self.player.current_song
            if song:
                self.notify(
                    f"{song.title}\n{song.artist} — {song.album}\n时长: {song.duration:.0f}秒",
                    title="歌曲信息",
                )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value
        cmd = parse_command(text)
        self._handle_command(cmd)
        cmd_input = self.query_one("#command-input", CommandInput)
        cmd_input.clear()

    def _handle_command(self, cmd: Command) -> None:
        if cmd.type == CommandType.PLAY:
            self.player.play()

        elif cmd.type == CommandType.PAUSE:
            self.player.pause()
            self._update_controls_ui()

        elif cmd.type == CommandType.STOP:
            self.player.stop()
            self._update_controls_ui()

        elif cmd.type == CommandType.NEXT:
            self.action_next_track()

        elif cmd.type == CommandType.PREVIOUS:
            self.action_previous_track()

        elif cmd.type == CommandType.VOLUME:
            try:
                vol = int(cmd.args) / 100
                self.player.set_volume(vol)
                self.notify(f"音量: {int(vol * 100)}%", title="音量")
            except ValueError:
                self.notify("用法: volume <0-100>", title="错误", severity="error")

        elif cmd.type == CommandType.SCAN:
            path = Path(cmd.args) if cmd.args else Path.home() / "Music"
            if path.exists():
                playlist = self.scanner.scan_to_playlist(path, name=path.name)
                name = playlist.name
                self._playlists[name] = playlist
                self._load_playlist_ui(playlist)
                self.notify(f"扫描完成: {len(playlist)} 首歌曲", title="扫描")
            else:
                self.notify(f"路径不存在: {path}", title="错误", severity="error")

        elif cmd.type == CommandType.PLAYLIST:
            if cmd.args in self._playlists:
                self._load_playlist_ui(self._playlists[cmd.args])
            else:
                self.notify(
                    f"歌单 '{cmd.args}' 不存在，请先用 scan 扫描",
                    title="错误",
                    severity="error",
                )

        elif cmd.type == CommandType.HELP:
            self.notify(
                "play  播放 | pause  暂停 | stop  停止\n"
                "next  下一曲 | prev  上一曲\n"
                "volume <0-100>  设置音量\n"
                "scan <路径>  扫描音乐文件夹\n"
                "playlist <名称>  加载歌单\n"
                "quit  退出",
                title="帮助",
            )

        elif cmd.type == CommandType.QUIT:
            self.exit()

        elif cmd.type == CommandType.UNKNOWN:
            self.notify(f"未知命令: {cmd.args or '?'}", title="错误", severity="error")

    def _load_playlist_ui(self, playlist: Playlist) -> None:
        playlist_panel = self.query_one("#playlist-panel", PlaylistPanel)
        playlist_panel.load_songs(playlist.songs)
        self.player.load_playlist(playlist.songs)
        self.title = f"Holle Music - {playlist.name}"
        self.notify(f"已加载歌单: {playlist.name} ({len(playlist)} 首)", title="歌单")


def main() -> None:
    """程序入口."""
    app = HolleMusicApp()
    app.run()
