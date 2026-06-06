"""Holle Music — Textual TUI 主应用."""

import threading
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Input, ListView
from textual.containers import Grid

from holle_music.models import Song, Playlist
from holle_music.scanner import Scanner
from holle_music.player import Player
from holle_music.widgets import (
    NowPlaying,
    PlaylistPanel,
    Controls,
    Visualizer,
    Equalizer,
    CommandInput,
    ChatBubbles,
    set_shimmer_palette,
    get_shimmer_palette,
)
from holle_music.minimax_api import MiniMaxService


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
    SEARCH = auto()
    COLOR = auto()
    UNKNOWN = auto()


@dataclass
class Command:
    type: CommandType
    args: str = ""


COMMAND_MAP: dict[str, CommandType] = {
    "/play": CommandType.PLAY,
    "/pause": CommandType.PAUSE,
    "/stop": CommandType.STOP,
    "/resume": CommandType.PLAY,
    "/next": CommandType.NEXT,
    "/prev": CommandType.PREVIOUS,
    "/previous": CommandType.PREVIOUS,
    "/volume": CommandType.VOLUME,
    "/vol": CommandType.VOLUME,
    "/scan": CommandType.SCAN,
    "/playlist": CommandType.PLAYLIST,
    "/help": CommandType.HELP,
    "/quit": CommandType.QUIT,
    "/exit": CommandType.QUIT,
    "/q": CommandType.QUIT,
    "/search": CommandType.SEARCH,
    "/color": CommandType.COLOR,
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
        grid-rows: 40fr 50fr 3;
        grid-columns: 1fr 1fr 1fr;
        height: 1fr;
        border: solid white;
    }

    PlaylistPanel {
        border: solid white;
        height: 100%;
        column-span: 1;
        row-span: 2;
        background: rgba(0, 0, 0, 0);
    }

    NowPlaying {
        border: solid white;
        height: 100%;
    }

    Controls Horizontal {
        height: auto;
    }

    #clock {
        width: 20;
        content-align: center middle;
        color: white;
    }

    .mode-btn {
        background: rgba(0,0,0,0);
        border: none;
        color: #888888;
        min-width: 3;
        width: auto;
        margin: 0 1;
    }

    .mode-btn:hover {
        color: white;
    }

    .mode-btn:focus {
        border: none;
        background: rgba(0,0,0,0);
        text-style: none;
        tint: rgba(0,0,0,0);
    }

    .active-mode {
        color: $accent;
        text-style: bold;
    }

    #controls-row {
        height: auto;
    }

    #controls-top {
        height: auto;
    }

    #controls-modes {
        height: auto;
    }

    #controls-modes > .mode-btn {
        margin: 0 1 0 0;
    }

    #mascot {
        margin-left: 2;
    }

    ChatBubbles {
        background: rgba(0, 0, 0, 0);
        color: white;
        width: 100%;
        height: 1fr;
        border: solid white;
        overflow-y: auto;
    }

    #np-header {
        height: auto;
    }

    #np-title {
        text-style: bold;
        width: auto;
        height: auto;
        content-align: left middle;
    }

    #np-artist {
        width: 1fr;
        content-align: left middle;
    }

    #np-album {
        width: 100%;
        content-align: left middle;
    }

    #np-progress {
        width: 100%;
        height: auto;
        padding: 0 0;
    }

    Controls {
        height: 100%;
    }

    .arrow-btn {
        background: rgba(0, 0, 0, 0);
        border: none;
        color: white;
        text-style: bold;
        width: auto;
        min-width: 3;
        margin: 0 0;
        text-align: center;
        content-align: center middle;
    }

    .arrow-btn:hover {
        text-opacity: 0.7;
    }

    Visualizer {
        border: solid white;
        height: 100%;
    }

    Equalizer {
        border: solid white;
        height: 100%;
    }

    CommandInput {
        column-span: 3;
        height: auto;
        border: solid white;
        padding: 0 0;
        background: rgba(0, 0, 0, 0);
        min-height: 3;
    }

    #cmd-help-hint {
        color: white;
        width: auto;
        content-align: left middle;
    }

    #cmd-prefix {
        color: white;
        width: auto;
        height: 1;
        content-align: left middle;
        padding: 0 0;
    }

    #cmd-input {
        border: none;
        color: white;
        width: 1fr;
        height: 1;
        padding: 0 0;
        content-align: left middle;
        background: rgba(0, 0, 0, 0);
    }

    ListView {
        color: white;
        background: rgba(0, 0, 0, 0);
    }

    ListView > ListItem {
        color: white;
        background: rgba(0, 0, 0, 0);
    }

    ListView > ListItem.--highlight {
        background: rgba(255, 255, 255, 0.15);
        color: white;
    }

    Input {
        color: white;
        border: none;
        padding: 0 1;
        background: rgba(0, 0, 0, 0);
    }

    Label {
        color: white;
    }

    Static {
        color: white;
    }

    Header {
        color: white;
    }

    Footer {
        color: white;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_play_pause", "播放/暂停"),
        Binding("p", "toggle_play_pause", "", show=False),
        Binding("key_media_play_pause", "toggle_play_pause", "", show=False),
        Binding("left", "previous_track", "上一曲"),
        Binding("b", "previous_track", "", show=False),
        Binding("ctrl+left", "previous_track", "", show=False),
        Binding("key_media_previous", "previous_track", "", show=False),
        Binding("right", "next_track", "下一曲"),
        Binding("n", "next_track", "", show=False),
        Binding("ctrl+right", "next_track", "", show=False),
        Binding("key_media_next", "next_track", "", show=False),
        Binding("tab", "focus_next", "切换焦点"),
        Binding("ctrl+d", "quit", "退出"),
        Binding("ctrl+c", "quit", "退出"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.player = Player()
        self.scanner = Scanner()
        self._playlists: dict[str, Playlist] = {}
        self._displayed_songs: list[Song] = []
        self._original_songs: list[Song] = []
        self._ai = MiniMaxService()
        self._current_music_dir = "E:/Music"
        self.player.on_song_change(self._on_song_changed)

    def compose(self) -> ComposeResult:
        yield Header()
        with Grid():
            yield NowPlaying(id="now-playing")
            yield Visualizer(id="visualizer")
            yield PlaylistPanel(id="playlist-panel")
            yield Controls(id="controls")
            yield Equalizer(id="equalizer")
            yield CommandInput(id="command-input")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Holle Music"
        self._load_color_setting()
        viz = self.query_one("#visualizer", Visualizer)
        viz.set_spectrum_source(self.player.get_current_spectrum)
        progress = self.query_one("#now-playing", NowPlaying).progress
        progress.set_on_seek(self._on_progress_seek)
        vol_bar = self.query_one("#visualizer", Visualizer).volume_bar
        vol_bar.set_volume(self.player.volume)
        vol_bar.set_on_change(self._on_volume_change)
        self.query_one("#command-input", CommandInput).set_prefix(self._current_music_dir)
        self._handle_command(Command(CommandType.SCAN))
        self.set_interval(1.0, self._check_song_end)
        self.set_interval(0.25, self._update_progress)

    # ── Song change ─────────────────────────────────────────────────

    def _on_song_changed(self, song: Song | None) -> None:
        if song is None:
            return
        np_widget = self.query_one("#now-playing", NowPlaying)
        np_widget.set_song(song)
        self._query_song_background(song)

    def _query_song_background(self, song: Song) -> None:
        prompt = (
            f"歌曲：《{song.title}》，歌手：{song.artist}。"
            f"请用2-3句话简要介绍这首歌的背景（创作故事、风格特点等）"
            f"和歌手的基本信息。直接输出内容，不要加'我正在听'等前缀。"
            f"用中文回答，简洁自然，不要用Markdown。"
        )

        def _run():
            try:
                result = self._ai.query_once(prompt)
                self.call_from_thread(self._on_song_bg_done, result)
            except Exception:
                self.call_from_thread(self._on_song_bg_error, "获取歌曲背景失败")

        threading.Thread(target=_run, daemon=True).start()

    def _on_song_bg_done(self, text: str) -> None:
        np_widget = self.query_one("#now-playing", NowPlaying)
        np_widget.set_song_info(text)

    def _on_song_bg_error(self, msg: str) -> None:
        np_widget = self.query_one("#now-playing", NowPlaying)
        np_widget.set_song_info_error(msg)

    # ── Progress bar ─────────────────────────────────────────────────

    def _update_progress(self) -> None:
        dur = self.player.get_duration()
        pos_ms = self.player.get_playback_position_ms()
        pos = pos_ms / 1000.0
        ratio = pos / dur if dur > 0 else 0.0
        progress = self.query_one("#now-playing", NowPlaying).progress
        progress.set_position(ratio, dur)

    def _on_progress_seek(self, seconds: float) -> None:
        self.player.seek(seconds)

    def _on_volume_change(self, vol: float) -> None:
        self.player.set_volume(vol)

    # ── Song end detection ──────────────────────────────────────────

    def _check_song_end(self) -> None:
        if self.player.has_ended():
            self.action_next_track()
            self._update_controls_ui()

    # ── Playback actions ────────────────────────────────────────────

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
        self.query_one("#controls", Controls).set_active(self.player.is_playing)
        viz = self.query_one("#visualizer", Visualizer)
        viz.set_active(self.player.is_playing)
        np_widget = self.query_one("#now-playing", NowPlaying)
        if self.player.is_playing:
            viz.start_shimmer()
            np_widget.start_shimmer()
        else:
            viz.stop_shimmer()
            np_widget.stop_shimmer()

    def _sync_playlist_selection(self) -> None:
        playlist = self.query_one("#playlist-panel", PlaylistPanel)
        lst = playlist.query_one("#playlist-list", ListView)
        lst.index = self.player.current_index

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.control.id != "playlist-list":
            return
        idx = event.control.index
        songs = self._displayed_songs or self.player.playlist
        if idx is not None and 0 <= idx < len(songs):
            song = songs[idx]
            self.player.play(song)
            self._update_controls_ui()

    # ── Mascot / Controls handlers ────────────────────────────────────

    def on_mascot_clicked(self, event) -> None:
        if event.zone == "prev":
            self.action_previous_track()
        elif event.zone == "toggle":
            self.action_toggle_play_pause()
        elif event.zone == "next":
            self.action_next_track()
        self._update_controls_ui()

    def on_controls_prev_next(self, event) -> None:
        if event.action == "prev":
            self.action_previous_track()
        elif event.action == "next":
            self.action_next_track()
        self._update_controls_ui()

    @on(Controls.ModeChange)
    def on_controls_mode_change(self, event: Controls.ModeChange) -> None:
        mode = event.mode
        self.player.set_play_mode(mode)
        panel = self.query_one("#playlist-panel", PlaylistPanel)
        if mode == "random":
            import random
            songs = list(self.player.playlist)
            if not songs:
                return
            cur = self.player.current_index
            current_song = songs.pop(cur)
            random.shuffle(songs)
            songs.insert(0, current_song)
            self.player.load_playlist(songs)
            self.player._current_index = 0
            panel.load_songs(songs)
            panel.border_title = "✻ Playlist ↬"
            self._displayed_songs = songs
            self._notify_chat("随机播放模式已开启")
        elif mode == "sequential":
            if self._original_songs:
                cur_song = self.player.current_song
                self.player.load_playlist(self._original_songs)
                if cur_song:
                    try:
                        idx = self._original_songs.index(cur_song)
                        self.player._current_index = idx
                    except ValueError:
                        pass
                panel.load_songs(self._original_songs)
            panel.border_title = "✻ Playlist ⭢"
            self._displayed_songs = []
            self._notify_chat("顺序播放模式已开启")
        elif mode == "repeat":
            panel.border_title = "✻ Playlist ⟳"
            self._notify_chat("单曲循环模式已开启")

    def on_mouse_move(self, event) -> None:
        self.query_one("#controls", Controls).update_mouse(
            event.screen_x, event.screen_y
        )

    # ── Command handler ─────────────────────────────────────────────

    def on_command_input_submitted(self, event: CommandInput.Submitted) -> None:
        text = event.text.strip()
        if not text:
            return
        if text.startswith("/"):
            cmd = parse_command(text)
            self._handle_command(cmd)
        else:
            self._chat_with_ai(text)

    def _notify_chat(self, msg: str) -> None:
        """Show notification as chat message."""
        try:
            chat = self.query_one("#chat-bubbles", ChatBubbles)
            chat.add_ai_msg(msg)
        except Exception:
            pass

    def _chat_with_ai(self, text: str) -> None:
        """Send user message to AI with web search results."""
        chat = self.query_one("#chat-bubbles", ChatBubbles)
        chat.add_user_msg(text)
        chat.set_pending()

        def _run():
            try:
                from datetime import datetime

                song = self.player.current_song
                now = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
                time_ctx = f"当前系统时间: {now}。"
                song_ctx = f"当前播放歌曲: {song.title} - {song.artist}。" if song else ""

                # 联网搜索（实时信息、天气、新闻等）
                try:
                    results = self._ai.search_web(text)
                except Exception:
                    results = ""

                prompt_parts = [time_ctx, song_ctx, f"用户问题: {text}"]
                if results:
                    prompt_parts.append(f"以下是通过联网搜索获得的实时参考信息，请优先依据这些信息回答:\n{results}")
                else:
                    prompt_parts.append("（联网搜索未返回结果，请根据你的知识和当前时间回答问题）")

                prompt = "\n\n".join(filter(None, prompt_parts))
                response = self._ai.chat(prompt)
                self.call_from_thread(lambda: chat.add_ai_msg(response))
            except Exception as e:
                self.call_from_thread(lambda: chat.add_ai_msg(f"请求失败: {e}"))

        threading.Thread(target=_run, daemon=True).start()

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
                self.query_one("#visualizer", Visualizer).volume_bar.set_volume(vol)
                self._notify_chat(f"音量: {int(vol * 100)}%")
            except ValueError:
                self._notify_chat("用法: /volume <0-100>")
        elif cmd.type == CommandType.SCAN:
            path = Path(cmd.args) if cmd.args else Path("E:/Music")
            if path.exists():
                self._current_music_dir = str(path.resolve())
                self.query_one("#command-input", CommandInput).set_prefix(self._current_music_dir)
                playlist = self.scanner.scan_to_playlist(path, name=path.name)
                name = playlist.name
                self._playlists[name] = playlist
                self._load_playlist_ui(playlist)
                self._notify_chat(f"扫描完成: {len(playlist)} 首歌曲")
            else:
                self._notify_chat(f"路径不存在: {path}")
        elif cmd.type == CommandType.PLAYLIST:
            if cmd.args in self._playlists:
                self._load_playlist_ui(self._playlists[cmd.args])
            else:
                self._notify_chat(f"歌单 '{cmd.args}' 不存在")
        elif cmd.type == CommandType.HELP:
            chat = self.query_one("#chat-bubbles", ChatBubbles)
            chat.add_user_msg("/help")
            chat.add_ai_msg(
                "/play  播放 | /pause  暂停\n"
                "/next  下一曲 | /prev  上一曲\n"
                "/volume <音量>  设置音量\n"
                "/scan [文件路径]  扫描音乐文件夹\n"
                "/search <关键词>  搜索歌曲\n"
                "/color <颜色>  选择闪烁颜色\n"
                "顺序⭢ 单曲⟳ 随机↬ | 空格 暂停\n"
                "/quit  退出"
            )
        elif cmd.type == CommandType.COLOR:
            name = cmd.args.strip().lower()
            if not name:
                self._notify_chat(
                    f"当前: {get_shimmer_palette()} | "
                    "可选: pink yellow red blue purple green orange gray brown black white colorful")
            elif set_shimmer_palette(name):
                self._save_color_setting(name)
                try:
                    self.query_one("#chat-bubbles", ChatBubbles).refresh()
                except Exception:
                    pass
                try:
                    self.query_one("#controls", Controls)._update_mode_buttons()
                except Exception:
                    pass
                self._notify_chat(f"闪烁颜色已切换为: {name}")
            else:
                self._notify_chat(
                    f"无效颜色 '{name}'。可选: pink yellow red blue purple green orange gray brown black white colorful")

        elif cmd.type == CommandType.SEARCH:
            self._search_songs(cmd.args)
        elif cmd.type == CommandType.QUIT:
            self.exit()
        elif cmd.type == CommandType.UNKNOWN:
            self._notify_chat(f"未知命令: {cmd.args or '?'}")

    # ── Playlist UI ─────────────────────────────────────────────────

    def _load_playlist_ui(self, playlist: Playlist) -> None:
        self._displayed_songs = []
        self._original_songs = list(playlist.songs)
        playlist_panel = self.query_one("#playlist-panel", PlaylistPanel)
        playlist_panel.load_songs(playlist.songs)
        self.player.load_playlist(playlist.songs)
        self.title = "Holle Music"

    def _search_songs(self, query: str) -> None:
        q = query.strip().lower()
        # 从原始完整列表搜索，避免在搜索结果上二次搜索
        all_songs = self._original_songs or self.player.playlist
        if not all_songs:
            self._notify_chat("播放列表为空")
            return
        if not q:
            self._restore_playlist_display()
            return
        results = [s for s in all_songs if q in s.title.lower() or q in s.artist.lower()]
        self._displayed_songs = results
        if results:
            # 将搜索结果设为当前播放列表
            self.player.load_playlist(results)
            panel = self.query_one("#playlist-panel", PlaylistPanel)
            panel.load_songs(results)
            panel.border_title = f'✻ Playlist | 搜索: "{query}"'
            self._notify_chat(f'搜索 "{query}" — {len(results)} 首')
        else:
            self._notify_chat(f'未找到 "{query}"')

    def _save_color_setting(self, name: str) -> None:
        import json
        try:
            cfg = Path(__file__).parent / ".holle_color.json"
            cfg.write_text(json.dumps({"color": name}))
        except Exception:
            pass

    def _load_color_setting(self) -> None:
        import json
        try:
            cfg = Path(__file__).parent / ".holle_color.json"
            if cfg.exists():
                data = json.loads(cfg.read_text())
                set_shimmer_palette(data.get("color", "pink"))
        except Exception:
            pass

    def _restore_playlist_display(self) -> None:
        songs = self._original_songs or self.player.playlist
        self._displayed_songs = []
        self.player.load_playlist(songs)
        panel = self.query_one("#playlist-panel", PlaylistPanel)
        panel.load_songs(songs)
        panel.border_title = "✻ Playlist"
        self._notify_chat(f"播放列表 ({len(songs)} 首)")


def main() -> None:
    """程序入口."""
    app = HolleMusicApp()
    app.run()
