"""AI tool executors for the Holle Music TUI.

These mirror the tools used by the desktop pet so that DeepSeek/Ark-based
AI services can control the terminal player through function calling.
"""

from __future__ import annotations

import json
from typing import Any

from holle_music.bilibili_searcher import BilibiliSearcher, is_network_error
from holle_music.models import Song
from holle_music.minimax_api import MiniMaxService


class TUITools:
    """Execute AI tool calls to control the TUI player and interface."""

    def __init__(self, app: Any) -> None:
        self._app = app
        self._last_search_results: list[dict] = []
        self._last_bilibili_results: list[Song] = []

    def execute(self, name: str, args: dict | str | None) -> str:
        """Dispatch a tool call by name and return a human-readable result."""
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            return f"未知工具: {name}"
        try:
            if isinstance(args, str):
                args = json.loads(args) if args.strip() else {}
            elif args is None:
                args = {}
            return handler(args)
        except Exception as exc:
            return f"执行失败: {exc}"

    @staticmethod
    def extract_play_query(text: str) -> str:
        """Strip playback-intent words to leave an artist or song title query."""
        noise = {
            "播放", "来一首", "听", "唱", "想听", "放", "点一首",
            "来一曲", "给我听", "一下", "呗", "的", "歌", "曲",
        }
        query = text
        for word in noise:
            query = query.replace(word, "")
        return query.strip()

    def auto_play_best_match(self, text: str, response: str = "") -> str:
        """Play the best matching recent search result when AI forgot to call play_song."""
        results = self._last_search_results
        if not results:
            return response

        chosen = None
        for source in (text, response):
            source_lower = source.lower()
            for song in results:
                if (song.title or "").lower() in source_lower:
                    chosen = song
                    break
            if chosen:
                break

        if not chosen:
            chosen = results[0]

        play_result = self.execute("play_song", {"title": chosen.title})
        if play_result.startswith("正在播放"):
            if response:
                return f"{response}\n\n{play_result}"
            return play_result
        return response

    def execute_plain_intent(self, text: str) -> str | None:
        """Try to handle common plain-text commands without LLM tool calling.

        Returns the tool result if a command was recognized, otherwise None.
        """
        import re

        t = text.strip().lower()
        if any(k in t for k in ("暂停", "别放", "stop")):
            return self.execute("toggle_play", {})
        if any(k in t for k in ("下一首", "下一曲", "下一")):
            return self.execute("next_track", {})
        if any(k in t for k in ("上一首", "上一曲", "上一")):
            return self.execute("prev_track", {})

        m = re.search(r"音量\s*(\d+)", text)
        if m:
            return self.execute("set_volume", {"volume": int(m.group(1))})
        if "音量" in t:
            return self.execute("get_volume", {})

        m = re.search(r"主题\s*(light|dark|明亮|暗黑)", text, re.IGNORECASE)
        if m:
            mode = "light" if m.group(1).lower() in ("light", "明亮") else "dark"
            return self.execute("set_main_color", {"mode": mode})

        m = re.search(r"颜色\s*(\w+)", text)
        if m:
            return self.execute("set_color", {"color": m.group(1)})

        m = re.search(r"模式\s*(顺序|单曲|随机|sequential|random|repeat)", text, re.IGNORECASE)
        if m:
            mode_map = {"顺序": "sequential", "单曲": "repeat", "随机": "random"}
            mode = mode_map.get(m.group(1), m.group(1).lower())
            return self.execute("set_mode", {"mode": mode})

        m = re.search(r"扫描\s*(.+)", text)
        if m:
            return self.execute("scan_music_folder", {"path": m.group(1).strip()})

        if any(k in t for k in ("在放什么", "当前歌曲", "正在播放")):
            return self.execute("get_current_song", {})
        if any(k in t for k in ("歌单", "列表")):
            return self.execute("get_playlist", {})

        return None

    def _tool_search_local(self, args: dict) -> str:
        """Search the current playlist for matching songs."""
        query = args.get("query", "").strip().lower()
        if not query:
            return "搜索关键词为空"

        songs = list(self._app._original_songs or self._app.player.playlist or [])
        if not songs:
            return "当前播放列表为空"

        results = []
        for song in songs:
            title = (song.title or "").lower()
            artist = (song.artist or "").lower()
            if query in title or query in artist:
                results.append(song)

        self._last_search_results = results

        if not results:
            return f'本地未找到 "{query}"'

        lines = [f'本地搜索 "{query}" 结果 ({len(results)} 首):']
        for i, song in enumerate(results[:10], 1):
            lines.append(f"{i}. {song.title} - {song.artist}")
        if len(results) > 10:
            lines.append(f"... 还有 {len(results) - 10} 首")
        lines.append("如果用户想播放其中一首，请调用 play_song 工具实际播放。")
        return "\n".join(lines)

    def _tool_search_bilibili(self, args: dict) -> str:
        """Search Bilibili for audio."""
        query = args.get("query", "").strip()
        if not query:
            return "搜索关键词为空"

        try:
            searcher = BilibiliSearcher()
            songs = searcher.search(query, max_results=args.get("max_results", 10))
        except Exception as exc:
            return "无法连接网络搜索 B 站" if is_network_error(exc) else f"B 站搜索失败: {exc}"

        self._last_bilibili_results = songs
        self._last_search_results = songs

        if not songs:
            return f'B 站未找到 "{query}"'

        lines = [f'B站搜索 "{query}" 结果 ({len(songs)} 首):']
        for i, song in enumerate(songs[:10], 1):
            lines.append(f"{i}. {song.title} - {song.artist}")
        if len(songs) > 10:
            lines.append(f"... 还有 {len(songs) - 10} 首")
        lines.append("如果用户想播放其中一首，请调用 play_song 工具实际播放。")
        return "\n".join(lines)

    def _tool_search_web(self, args: dict) -> str:
        """Search the web using DuckDuckGo."""
        query = args.get("query", "").strip()
        if not query:
            return "搜索关键词为空"

        results = MiniMaxService.search_web(query)
        if not results:
            return "联网搜索未返回结果"
        return results

    def _play_bilibili_song(self, song) -> str:
        from holle_music.online_cache import audio_path, is_cached

        if is_cached(song.bvid):
            cached = audio_path(song.bvid)
            song.path = cached
            self._app.call_from_thread(lambda: (
                self._app.player.play(song),
                self._app._update_controls_ui(),
                self._app._sync_playlist_selection(),
            ))
            return f"正在播放: {song.title} - {song.artist}"

        self._app._notify_chat(f"{song.title} 正在下载...")

        def _download_and_play():
            try:
                searcher = BilibiliSearcher(progress_callback=self._app._notify_chat)
                cached = searcher.download_audio(song)
                song.path = cached
                self._app.call_from_thread(lambda: (
                    self._app.player.play(song),
                    self._app._update_controls_ui(),
                    self._app._sync_playlist_selection(),
                    self._app._notify_chat(f"正在播放: {song.title} - {song.artist}"),
                ))
            except Exception as exc:
                msg = "下载失败，请检查网络" if is_network_error(exc) else str(exc)
                self._app.call_from_thread(lambda: self._app._notify_chat(f"{song.title} {msg}"))

        import threading
        threading.Thread(target=_download_and_play, daemon=True).start()
        return f"正在准备播放: {song.title} - {song.artist} 稍等一会..."

    def _tool_play_song(self, args: dict) -> str:
        """Play a song by title (and optional artist)."""
        title = args.get("title", "").strip()
        artist = args.get("artist", "").strip()
        if not title:
            return "歌曲标题为空"

        # Try Bilibili results first.
        for song in self._last_bilibili_results:
            s_title = (song.title or "").strip()
            s_artist = (song.artist or "").strip()
            if title.lower() in s_title.lower():
                if not artist or artist.lower() in s_artist.lower():
                    return self._play_bilibili_song(song)

        # Try recent local search results first.
        for song in self._last_search_results:
            if title.lower() in (song.title or "").lower():
                if not artist or artist.lower() in (song.artist or "").lower():
                    self._app.player.play(song)
                    self._app._update_controls_ui()
                    self._app._sync_playlist_selection()
                    return f"正在播放: {song.title} - {song.artist}"

        # Fall back to a title search across the full playlist.
        songs = list(self._app._original_songs or self._app.player.playlist or [])
        for song in songs:
            if title.lower() in (song.title or "").lower():
                if not artist or artist.lower() in (song.artist or "").lower():
                    self._app.player.play(song)
                    self._app._update_controls_ui()
                    self._app._sync_playlist_selection()
                    return f"正在播放: {song.title} - {song.artist}"

        return f"未找到歌曲: {title}" + (f" - {artist}" if artist else "")

    def _tool_play_artist(self, args: dict) -> str:
        """Play all songs by a given artist."""
        artist = args.get("artist", "").strip()
        if not artist:
            return "歌手名为空"

        songs = list(self._app._original_songs or self._app.player.playlist or [])
        matches = [
            s for s in songs
            if artist.lower() in (s.artist or "").lower()
        ]
        if not matches:
            return f'本地未找到歌手 "{artist}"'

        self._app.player.load_playlist(matches)
        self._app.player.play(matches[0])
        self._app._displayed_songs = list(matches)
        try:
            from holle_music.widgets import PlaylistPanel
            panel = self._app.query_one("#playlist-panel", PlaylistPanel)
            panel.load_songs(matches)
            panel.border_title = f'✻ Playlist | 歌手: "{artist}"'
        except Exception:
            pass
        self._app._update_controls_ui()
        self._app._sync_playlist_selection()
        return f'已加载 {len(matches)} 首 "{artist}" 的歌曲，正在播放: {matches[0].title}'

    def _tool_restore_playlist(self, _args: dict) -> str:
        """Restore the full original playlist."""
        songs = self._app._original_songs
        if not songs:
            return "没有可恢复的歌单"
        self._app.player.load_playlist(songs)
        self._app._displayed_songs = list(songs)
        try:
            from holle_music.widgets import PlaylistPanel
            panel = self._app.query_one("#playlist-panel", PlaylistPanel)
            panel.load_songs(songs)
            panel.border_title = "✻ Playlist"
        except Exception:
            pass
        return "已恢复全部歌单"

    def _tool_toggle_play(self, _args: dict) -> str:
        """Toggle play / pause."""
        self._app.action_toggle_play_pause()
        return "已播放" if self._app.player.is_playing else "已暂停"

    def _tool_next_track(self, _args: dict) -> str:
        """Skip to the next track."""
        self._app.action_next_track()
        song = self._app.player.current_song
        if song:
            return f"下一曲: {song.title} - {song.artist}"
        return "已切换到下一曲"

    def _tool_prev_track(self, _args: dict) -> str:
        """Go back to the previous track."""
        self._app.action_previous_track()
        song = self._app.player.current_song
        if song:
            return f"上一曲: {song.title} - {song.artist}"
        return "已切换到上一曲"

    def _tool_set_volume(self, args: dict) -> str:
        """Set volume (0-100)."""
        try:
            volume = int(args.get("volume", 50))
        except (TypeError, ValueError):
            return "音量值无效，请输入 0-100 的整数"

        volume = max(0, min(100, volume))
        vol = volume / 100.0
        self._app.player.set_volume(vol)
        from holle_music.settings import set_setting

        set_setting("volume", vol)
        try:
            from holle_music.widgets import Visualizer

            viz = self._app.query_one("#visualizer", Visualizer)
            viz.volume_bar.set_volume(vol)
        except Exception:
            pass
        return f"音量已设置为 {volume}%"

    def _tool_set_mode(self, args: dict) -> str:
        """Set play mode (sequential / random / repeat)."""
        mode = args.get("mode", "").strip().lower()
        valid_modes = {"sequential", "random", "repeat"}
        if mode not in valid_modes:
            return f"无效模式 '{mode}'，可选: sequential, random, repeat"

        self._app.player.set_play_mode(mode)
        from holle_music.settings import set_setting

        set_setting("play_mode", mode)
        try:
            self._app.query_one("#controls", self._app.Controls).set_mode(mode)
        except Exception:
            pass
        labels = {
            "sequential": "顺序播放",
            "random": "随机播放",
            "repeat": "单曲循环",
        }
        return f"播放模式已切换为: {labels.get(mode, mode)}"

    def _tool_get_current_song(self, _args: dict) -> str:
        """Return information about the currently playing song."""
        song = self._app.player.current_song
        if not song:
            return "当前没有播放歌曲"
        status = "播放中" if self._app.player.is_playing else "已暂停"
        return f"当前歌曲: {song.title} - {song.artist} ({status})"

    def _tool_get_playlist(self, _args: dict) -> str:
        """Return the current playlist."""
        playlist = list(self._app.player.playlist or [])
        if not playlist:
            return "当前播放列表为空"

        lines = [f"播放列表 ({len(playlist)} 首):"]
        for i, song in enumerate(playlist[:20], 1):
            lines.append(f"{i}. {song.title} - {song.artist}")
        if len(playlist) > 20:
            lines.append(f"... 还有 {len(playlist) - 20} 首")
        return "\n".join(lines)

    def _tool_get_volume(self, _args: dict) -> str:
        """Return the current volume."""
        vol = int(self._app.player.volume * 100)
        return f"当前音量: {vol}%"

    def _tool_set_color(self, args: dict) -> str:
        """Set the shimmer color."""
        name = args.get("color", "").strip().lower()
        if not name:
            return "颜色名不能为空"
        from holle_music.widgets import set_shimmer_palette
        from holle_music.settings import set_setting
        from holle_music.widgets import restart_active_shimmers

        if set_shimmer_palette(name):
            set_setting("color", name)
            self._app._save_color_setting(name)
            try:
                restart_active_shimmers(self._app.screen)
                self._app.screen.refresh()
            except Exception:
                pass
            return f"闪烁颜色已切换为: {name}"
        valid = ", ".join(sorted(self._valid_colors()))
        return f"无效颜色 '{name}'，可选: {valid}"

    @staticmethod
    def _valid_colors() -> list[str]:
        from holle_music.shared import _SHIMMER_PALETTES
        return list(_SHIMMER_PALETTES.keys())

    def _tool_set_main_color(self, args: dict) -> str:
        """Set the main UI color theme."""
        name = args.get("mode", "").strip().lower()
        if name not in ("light", "dark"):
            return "无效主体配色，可选: light / dark"
        from holle_music.settings import set_setting

        set_setting("main_color", name)
        try:
            self._app.query_one("#controls", self._app.Controls).set_main_color(name)
        except Exception:
            pass
        return f"主体配色已切换为: {name}"

    def _tool_scan_music_folder(self, args: dict) -> str:
        """Scan a music folder and load it into the playlist."""
        from holle_music.settings import set_setting

        path_str = args.get("path", "").strip()
        path = Path(path_str) if path_str else Path(self._app._current_music_dir)
        if not path.exists():
            return f"路径不存在: {path}"
        try:
            playlist = self._app.scanner.scan_to_playlist(path, name=path.name)
            self._app._current_music_dir = str(path.resolve())
            set_setting("music_dir", self._app._current_music_dir)
            self._app.query_one("#command-input", self._app.CommandInput).set_prefix(
                self._app._current_music_dir
            )
            self._app._load_playlist_ui(playlist)
            return f"已扫描 {len(playlist)} 首歌曲"
        except Exception as exc:
            return f"扫描失败: {exc}"
