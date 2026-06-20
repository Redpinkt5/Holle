"""AI tool executors for Holle Pet — bridge DeepSeek function calls to player actions.

AITools receives tool-call requests from DeepSeekService and dispatches them to
PetPlayer via IPC or direct method calls.
"""

from __future__ import annotations

import json
from typing import Any

from holle_music.minimax_api import MiniMaxService


class AITools:
    """Execute AI tool calls to control the music player.

    Args:
        player: PetPlayer instance used for IPC and state queries.
    """

    def __init__(self, player: Any, window: Any = None) -> None:
        self._player = player
        self._window = window
        self._last_search_results: list[dict] = []

    def set_window(self, window: Any) -> None:
        """Set the pet window reference so color tools can trigger a redraw."""
        self._window = window

    # ── Public API ────────────────────────────────────────────────────────

    def execute(self, name: str, args: dict | str | None) -> str:
        """Dispatch a tool call by name and return a human-readable result.

        Args:
            name: Tool name (e.g. "play_song", "toggle_play").
            args: Arguments dict parsed from the AI's function call, or a JSON
                string when the provider returns raw function arguments.

        Returns:
            Result string for the AI to consume, or an error message.
        """
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

    def auto_play_best_match(self, text: str, response: str = "", query: str = "") -> str:
        """Pick the best matching recent search result and play it.

        This is a fallback for when the AI searched but forgot to call
        ``play_song``. Returns the original response with a playback note.
        """
        results = self._last_search_results
        if not results:
            return response

        # If multiple results all match the query as an artist, load the artist playlist.
        lowered_query = query.lower()
        if (
            len(results) > 1
            and lowered_query
            and all(
                lowered_query in (song.get("artist") or "").lower()
                for song in results
            )
        ):
            return self.execute("play_artist", {"artist": query})

        chosen = None
        for source in (text, response):
            source_lower = source.lower()
            for song in results:
                if (song.get("title") or "").lower() in source_lower:
                    chosen = song
                    break
            if chosen:
                break

        if not chosen:
            chosen = results[0]

        play_result = self.execute(
            "play_song", {"title": chosen.get("title", "")}
        )
        if play_result.startswith(("正在播放", "尝试播放")):
            if response:
                return f"{response}\n\n{play_result}"
            return play_result
        return response

    def execute_plain_intent(self, text: str) -> str | None:
        """Try to handle common plain-text commands without LLM tool calling."""
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

        m = re.search(r"颜色\s*(\w+)", text)
        if m:
            return self.execute("set_color", {"color": m.group(1)})

        m = re.search(r"主题\s*(light|dark|明亮|暗黑)", text, re.IGNORECASE)
        if m:
            mode = "light" if m.group(1).lower() in ("light", "明亮") else "dark"
            return self.execute("set_main_color", {"mode": mode})

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

    # ── Tool implementations ──────────────────────────────────────────────

    def _tool_search_local(self, args: dict) -> str:
        """Search the current playlist for matching songs."""
        query = args.get("query", "").strip().lower()
        if not query:
            return "搜索关键词为空"

        state = self._player.get_state()
        playlist = state.get("playlist", [])
        if not playlist:
            return "当前播放列表为空"

        results = []
        for song in playlist:
            title = (song.get("title") or "").lower()
            artist = (song.get("artist") or "").lower()
            if query in title or query in artist:
                results.append(song)

        self._last_search_results = results

        if not results:
            return f'本地未找到 "{query}"'

        lines = [f'本地搜索 "{query}" 结果 ({len(results)} 首):']
        for i, song in enumerate(results[:10], 1):
            title = song.get("title", "未知")
            artist = song.get("artist", "未知")
            lines.append(f"{i}. {title} - {artist}")
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

        # Try to match from recent local search results first
        for song in self._last_search_results:
            s_title = (song.get("title") or "").strip()
            s_artist = (song.get("artist") or "").strip()
            if title.lower() in s_title.lower():
                if not artist or artist.lower() in s_artist.lower():
                    self._player.play_song(song)
                    return f"正在播放: {s_title} - {s_artist}"

        # Fall back to sending the raw title
        payload = {"title": title}
        if artist:
            payload["artist"] = artist
        self._player.play_song(payload)
        return f"尝试播放: {title}" + (f" - {artist}" if artist else "")

    def _tool_play_artist(self, args: dict) -> str:
        """Play all songs by a given artist."""
        artist = args.get("artist", "").strip()
        if not artist:
            return "歌手名为空"

        state = self._player.get_state()
        playlist = state.get("playlist", [])
        matches = [
            s for s in playlist
            if artist.lower() in (s.get("artist") or "").lower()
        ]
        if not matches:
            return f'本地未找到歌手 "{artist}"'

        self._player.play_artist(artist)
        return f'已加载 {len(matches)} 首 "{artist}" 的歌曲，正在播放: {matches[0].get("title", "未知")}'

    def _tool_restore_playlist(self, _args: dict) -> str:
        """Restore the full original playlist."""
        try:
            self._player.restore_playlist()
            return "已恢复全部歌单"
        except Exception as exc:
            return f"恢复歌单失败: {exc}"

    def _tool_toggle_play(self, _args: dict) -> str:
        """Toggle play / pause."""
        self._player.toggle_play()
        state = self._player.get_state()
        playing = state.get("playing", False)
        return "已播放" if playing else "已暂停"

    def _tool_next_track(self, _args: dict) -> str:
        """Skip to the next track."""
        self._player.next_track()
        state = self._player.get_state()
        song = state.get("song")
        if song:
            return f"下一曲: {song.get('title', '未知')} - {song.get('artist', '未知')}"
        return "已切换到下一曲"

    def _tool_prev_track(self, _args: dict) -> str:
        """Go back to the previous track."""
        self._player.prev_track()
        state = self._player.get_state()
        song = state.get("song")
        if song:
            return f"上一曲: {song.get('title', '未知')} - {song.get('artist', '未知')}"
        return "已切换到上一曲"

    def _tool_set_volume(self, args: dict) -> str:
        """Set volume (0-100)."""
        try:
            volume = int(args.get("volume", 50))
        except (TypeError, ValueError):
            return "音量值无效，请输入 0-100 的整数"

        volume = max(0, min(100, volume))
        self._player.set_volume_pct(volume)
        return f"音量已设置为 {volume}%"

    def _tool_set_mode(self, args: dict) -> str:
        """Set play mode (sequential / random / repeat)."""
        mode = args.get("mode", "").strip().lower()
        valid_modes = {"sequential", "random", "repeat"}
        if mode not in valid_modes:
            return f"无效模式 '{mode}'，可选: sequential, random, repeat"
        self._player.set_mode(mode)
        mode_labels = {
            "sequential": "顺序播放",
            "random": "随机播放",
            "repeat": "单曲循环",
        }
        return f"播放模式已切换为: {mode_labels.get(mode, mode)}"

    def _tool_get_current_song(self, _args: dict) -> str:
        """Return information about the currently playing song."""
        state = self._player.get_state()
        song = state.get("song")
        if not song:
            return "当前没有播放歌曲"
        title = song.get("title", "未知")
        artist = song.get("artist", "未知")
        playing = state.get("playing", False)
        status = "播放中" if playing else "已暂停"
        return f"当前歌曲: {title} - {artist} ({status})"

    def _tool_get_playlist(self, _args: dict) -> str:
        """Return the current playlist."""
        state = self._player.get_state()
        playlist = state.get("playlist", [])
        if not playlist:
            return "当前播放列表为空"

        lines = [f"播放列表 ({len(playlist)} 首):"]
        for i, song in enumerate(playlist[:20], 1):
            title = song.get("title", "未知")
            artist = song.get("artist", "未知")
            lines.append(f"{i}. {title} - {artist}")
        if len(playlist) > 20:
            lines.append(f"... 还有 {len(playlist) - 20} 首")
        return "\n".join(lines)

    def _tool_get_volume(self, _args: dict) -> str:
        """Return the current volume."""
        vol = int(self._player.volume * 100)
        return f"当前音量: {vol}%"

    def _tool_set_color(self, args: dict) -> str:
        """Set the shimmer color."""
        name = args.get("color", "").strip().lower()
        if not name:
            return "颜色名不能为空"
        from holle_music.shared import set_shimmer_palette, _SHIMMER_PALETTES
        from holle_music.settings import set_setting

        if set_shimmer_palette(name):
            set_setting("color", name)
            if self._player._is_main_app_running():
                self._player._send_cmd(f"color:{name}")
            if self._window is not None:
                try:
                    self._window._update_display()
                except Exception:
                    pass
            return f"闪烁颜色已切换为: {name}"
        valid = ", ".join(sorted(_SHIMMER_PALETTES.keys()))
        return f"无效颜色 '{name}'，可选: {valid}"

    def _tool_set_main_color(self, args: dict) -> str:
        """Set the main UI color theme."""
        name = args.get("mode", "").strip().lower()
        if name not in ("light", "dark"):
            return "无效主体配色，可选: light / dark"
        from holle_music.settings import set_setting

        set_setting("main_color", name)
        if self._player._is_main_app_running():
            self._player._send_cmd(f"maincolor:{name}")
        if self._window is not None:
            try:
                self._window.set_main_color(name)
            except Exception:
                pass
        return f"主体配色已切换为: {name}"

    def _tool_scan_music_folder(self, args: dict) -> str:
        """Scan a music folder and load it into the playlist."""
        from pathlib import Path
        from holle_music.settings import set_setting

        path_str = args.get("path", "").strip()
        path = Path(path_str) if path_str else Path("E:/Music")
        if not path.exists():
            return f"路径不存在: {path}"
        try:
            from holle_music.scanner import Scanner
            scanner = Scanner()
            playlist = scanner.scan_to_playlist(path, name=path.name)
            songs = list(playlist.songs)
            self._player.load_playlist(songs)
            set_setting("music_dir", str(path.resolve()))
            return f"已扫描 {len(songs)} 首歌曲"
        except Exception as exc:
            return f"扫描失败: {exc}"
