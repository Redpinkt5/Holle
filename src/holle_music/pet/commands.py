"""Pet input commands — slash/shorthand commands for the desktop pet input box."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable

from holle_music.ai_provider import (
    PROVIDERS,
    create_ai_service,
    detect_provider,
    parse_ai_args,
)
from holle_music.scanner import Scanner
from holle_music.settings import set_setting
from holle_music.shared import set_shimmer_palette


class PetCommandHandler:
    """Parse and execute commands typed into the pet input box.

    Anything that looks like a command is handled locally; everything else is
    forwarded to the AI chat handler.
    """

    def __init__(
        self,
        player: Any,
        tools: Any,
        window: Any,
        ai_config_callback: Callable[[str, str, str | None], tuple[bool, str | None]]
        | None = None,
    ) -> None:
        self._player = player
        self._tools = tools
        self._window = window
        self._ai_config_callback = ai_config_callback

    def try_handle(self, text: str) -> tuple[bool, str]:
        """Try to handle ``text`` as a command.

        Returns (handled, message). ``message`` is non-empty when the command
        produced a result that should be shown to the user.
        """
        if not text:
            return False, ""

        # Space is a valid pause shortcut, but strip() would remove it.
        if text == " ":
            return True, self._execute("pause", "")

        text = text.strip()
        if not text:
            return False, ""

        parsed = self._parse(text)
        if parsed is None:
            return False, ""

        cmd, arg = parsed
        result = self._execute(cmd, arg)
        return True, result

    def _parse(self, text: str) -> tuple[str, str] | None:
        """Parse command text into (cmd, arg) or None if not a command."""
        # Slash commands: /cmd arg
        if text.startswith("/"):
            rest = text[1:].strip()
            parts = rest.split(None, 1)
            cmd = parts[0].lower() if parts else ""
            arg = parts[1] if len(parts) > 1 else ""
            # /model selects the AI model; /mode selects the play mode.
            if cmd == "model":
                cmd = "aimodel"
            return cmd, arg

        # Single-character / keyword shortcuts
        shortcuts: dict[str, tuple[str, str]] = {
            " ": ("pause", ""),
            "+": ("next", ""),
            "-": ("prev", ""),
            "quit": ("quit", ""),
            "exit": ("quit", ""),
            "退出": ("quit", ""),
            "help": ("help", ""),
            "帮助": ("help", ""),
            "播放": ("play", ""),
            "暂停": ("pause", ""),
            "下一曲": ("next", ""),
            "上一曲": ("prev", ""),
            "顺序": ("mode", "sequential"),
            "单曲": ("mode", "repeat"),
            "随机": ("mode", "random"),
            # Chinese command aliases without slash
            "音量": ("volume", ""),
            "扫描": ("scan", ""),
            "搜索": ("search", ""),
            "颜色": ("color", ""),
            "模式": ("mode", ""),
            "恢复": ("restore", ""),
        }

        if text in shortcuts:
            return shortcuts[text]

        return None

    def _execute(self, cmd: str, arg: str) -> str:
        """Execute a parsed command and return a response message."""
        if cmd in ("play", "pause"):
            return self._cmd_play_pause(cmd)
        if cmd == "next":
            return self._cmd_next()
        if cmd == "prev":
            return self._cmd_prev()
        if cmd == "volume":
            return self._cmd_volume(arg)
        if cmd == "scan":
            return self._cmd_scan(arg)
        if cmd == "search":
            return self._cmd_search(arg)
        if cmd == "color":
            return self._cmd_color(arg)
        if cmd == "maincolor":
            return self._cmd_maincolor(arg)
        if cmd == "ai":
            return self._cmd_ai(arg)
        if cmd == "aimodel":
            return self._cmd_aimodel(arg)
        if cmd == "restore":
            return self._cmd_restore()
        if cmd == "mode":
            return self._cmd_mode(arg)
        if cmd == "quit":
            return self._cmd_quit()
        if cmd == "help":
            return self._cmd_help()
        return f"未知命令: /{cmd}，输入 /help 查看帮助"

    def _cmd_play_pause(self, cmd: str) -> str:
        is_playing = self._player.is_playing
        print(f"[PET] /{cmd}: is_playing={is_playing}, main_app={self._player._is_main_app_running()}")
        if cmd == "play" and is_playing:
            return "已经在播放中"
        if cmd == "pause" and not is_playing:
            return "当前已暂停"
        self._player.toggle_play()
        return "已播放" if not is_playing else "已暂停"

    def _cmd_next(self) -> str:
        self._player.next_track()
        state = self._player.get_state()
        song = state.get("song")
        if song:
            return f"下一曲: {song.get('title', '未知')} - {song.get('artist', '未知')}"
        return "已切换到下一曲"

    def _cmd_prev(self) -> str:
        self._player.prev_track()
        state = self._player.get_state()
        song = state.get("song")
        if song:
            return f"上一曲: {song.get('title', '未知')} - {song.get('artist', '未知')}"
        return "已切换到上一曲"

    def _cmd_volume(self, arg: str) -> str:
        arg = arg.strip()
        if not arg:
            vol = int(self._player.volume * 100)
            return f"当前音量: {vol}%"
        try:
            vol = int(arg)
        except ValueError:
            return "音量值无效，请输入 0-100 的整数，例如 /volume 50"
        vol = max(0, min(100, vol))
        # Update local player state immediately and notify main app if running.
        if self._player._is_main_app_running():
            self._player._send_cmd(f"volume:{vol}")
        else:
            self._player.set_volume(vol / 100.0)
        # Persist the volume setting for next session.
        set_setting("volume", vol / 100.0)
        # Refresh window to update volume-based shimmer.
        try:
            self._window.set_volume(vol / 100.0)
        except Exception:
            pass
        return f"音量已设置为 {vol}%"

    def _cmd_scan(self, arg: str) -> str:
        path = arg.strip() or "E:/Music"
        p = Path(path)
        if not p.exists():
            return f"路径不存在: {path}"
        try:
            scanner = Scanner()
            playlist = scanner.scan_to_playlist(p, name=p.name)
            songs = list(playlist.songs)
            self._player.load_playlist(songs)
            # Persist the directory for next startup.
            from holle_music.settings import set_setting
            set_setting("music_dir", str(p.resolve()))
            return f"已扫描 {len(songs)} 首歌曲"
        except Exception as exc:
            return f"扫描失败: {exc}"

    def _cmd_search(self, arg: str) -> str:
        query = arg.strip()
        if not query:
            return "请输入搜索关键词，例如 /search 周杰伦"
        result = self._tools.execute("search_local", {"query": query})
        return result

    def _cmd_color(self, arg: str) -> str:
        name = arg.strip().lower()
        if not name:
            return "请输入颜色名，例如 /color blue"
        if set_shimmer_palette(name):
            set_setting("color", name)
            # Notify the main app if it is running so both sides stay in sync.
            if self._player._is_main_app_running():
                self._player._send_cmd(f"color:{name}")
            try:
                self._window._update_display()
            except Exception:
                pass
            return f"闪烁颜色已切换为: {name}"
        valid = ", ".join(sorted(self._valid_colors()))
        return f"无效颜色 '{name}'，可选: {valid}"

    @staticmethod
    def _valid_colors() -> list[str]:
        from holle_music.shared import _SHIMMER_PALETTES
        return list(_SHIMMER_PALETTES.keys())

    def _cmd_maincolor(self, arg: str) -> str:
        name = arg.strip().lower()
        if not name:
            cur = getattr(self._window, '_main_color', 'light')
            return f"当前主颜色: {cur}，可选: light / dark"
        if name not in ("light", "dark"):
            return f"无效颜色 '{name}'，可选: light / dark"
        set_setting("main_color", name)
        if self._player._is_main_app_running():
            self._player._send_cmd(f"maincolor:{name}")
        try:
            self._window.set_main_color(name)
        except Exception:
            pass
        return f"主颜色已切换为: {name}"

    def _cmd_ai(self, arg: str) -> str:
        """Handle /ai <apikey> to configure the shared AI provider."""
        key = arg.strip()
        if not key:
            return "用法: /ai <你的 API Key>"

        def _detect_and_set():
            provider = detect_provider(key)
            if not provider:
                self._window.show_response_bubble("无法识别该 API Key 对应的供应商，请检查 key 是否正确")
                return

            config = PROVIDERS[provider]
            model = config["model"]
            set_setting("ai_provider", provider)
            set_setting("ai_api_key", key)
            set_setting("ai_base_url", config["base_url"])
            set_setting("ai_model", model)

            if self._ai_config_callback is not None:
                ok, err = self._ai_config_callback(provider, key, None)
                if ok:
                    self._window.show_response_bubble(f"AI 已配置为: {provider} / {model}")
                else:
                    self._window.show_response_bubble(f"AI 初始化失败: {err}")
            else:
                self._window.show_response_bubble(f"AI 已配置为: {provider} / {model}")

        threading.Thread(target=_detect_and_set, daemon=True).start()
        return "正在识别供应商..."

    def _cmd_aimodel(self, arg: str) -> str:
        """Handle /model <model> to switch the AI model."""
        model_name = arg.strip()
        if not model_name:
            from holle_music.settings import load_settings
            current = load_settings().get("ai_model", "默认")
            return f"当前模型: {current} | 用法: /model <模型名>"

        from holle_music.settings import load_settings
        settings = load_settings()
        provider = settings.get("ai_provider")
        api_key = settings.get("ai_api_key")
        if not provider or not api_key:
            return "请先使用 /ai <你的 API Key> 配置 AI"

        set_setting("ai_model", model_name)
        if self._ai_config_callback is not None:
            ok, err = self._ai_config_callback(provider, api_key, model_name)
            if ok:
                return f"模型已切换为: {model_name}"
            return f"模型切换失败: {err}"
        return f"模型已切换为: {model_name}"

    def _cmd_mode(self, arg: str) -> str:
        arg = arg.strip().lower()
        aliases = {
            "顺序": "sequential",
            "单曲": "repeat",
            "随机": "random",
            "sequential": "sequential",
            "random": "random",
            "repeat": "repeat",
        }
        mode = aliases.get(arg)
        if not mode:
            return "模式无效，可选: 顺序(sequential) / 单曲(repeat) / 随机(random)"

        if self._player._is_main_app_running():
            self._player._send_cmd(f"mode:{mode}")
        else:
            self._player.cycle_mode()
        labels = {"sequential": "顺序播放", "random": "随机播放", "repeat": "单曲循环"}
        return f"播放模式已切换为: {labels.get(mode, mode)}"

    def _cmd_restore(self) -> str:
        """Restore the full original playlist after an artist filter."""
        try:
            self._player.restore_playlist()
            return "已恢复全部歌单"
        except Exception as exc:
            return f"恢复歌单失败: {exc}"

    def _cmd_quit(self) -> str:
        try:
            self._window.close()
        except Exception:
            pass
        return ""

    def _cmd_help(self) -> str:
        return (
            "可用命令:\n"
            "/play 播放 | /pause 暂停 | 空格 暂停\n"
            "/next 下一曲 | /prev 上一曲 | + 下一曲 | - 上一曲\n"
            "/volume <0-100> 设置音量 | /volume 查看音量\n"
            "/scan <路径> 扫描音乐文件夹\n"
            "/search <关键词> 搜索本地歌曲\n"
            "/color <颜色> 切换闪烁颜色\n"
            "/maincolor <light/dark> 切换主体配色\n"
            "/ai <API Key> 配置 AI\n"
            "/model <模型名> 切换 AI 模型\n"
            "/restore 恢复全部歌单\n"
            "顺序 / 单曲 / 随机 切换播放模式\n"
            "quit 退出 | /help 帮助"
        )
