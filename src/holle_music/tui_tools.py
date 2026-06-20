"""AI tool executors for the Holle Music TUI.

These mirror the tools used by the desktop pet so that DeepSeek/Ark-based
AI services can control the terminal player through function calling.
"""

from __future__ import annotations

import json
from typing import Any

from holle_music.minimax_api import MiniMaxService


class TUITools:
    """Execute AI tool calls to control the TUI player and interface."""

    def __init__(self, app: Any) -> None:
        self._app = app
        self._last_search_results: list[dict] = []

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

    def _tool_search_web(self, args: dict) -> str:
        """Search the web using DuckDuckGo."""
        query = args.get("query", "").strip()
        if not query:
            return "搜索关键词为空"

        results = MiniMaxService.search_web(query)
        if not results:
            return "联网搜索未返回结果"
        return results

    def _tool_play_song(self, args: dict) -> str:
        """Play a song by title (and optional artist)."""
        title = args.get("title", "").strip()
        artist = args.get("artist", "").strip()
        if not title:
            return "歌曲标题为空"

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
