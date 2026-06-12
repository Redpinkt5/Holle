"""PetPlayer — 桌面宠物播放控制器，支持独立播放或 IPC 代理到主程序."""

import json
import time
from pathlib import Path

from holle_music.models import Song
from holle_music.player import Player


class PetPlayer:
    """桌面宠物播放器。

    当主程序运行时，通过 IPC 文件（~/.holle_music/pet_state.json 和
    pet_cmd.json）与主程序通信；主程序未运行时，回退到独立播放模式。
    """

    _MODES = ["sequential", "random", "repeat"]

    def __init__(self) -> None:
        self._mode_index = 0
        self._standalone_player: Player | None = None
        self._cached_state: dict = {}

    @property
    def _ipc_dir(self) -> Path:
        return Path.home() / ".holle_music"

    @property
    def _state_file(self) -> Path:
        return self._ipc_dir / "pet_state.json"

    @property
    def _cmd_file(self) -> Path:
        return self._ipc_dir / "pet_cmd.json"

    @property
    def mode(self) -> str:
        if self._is_main_app_running():
            state = self.get_state()
            mode = state.get("mode", "")
            if mode in self._MODES:
                self._mode_index = self._MODES.index(mode)
                return mode
        return self._MODES[self._mode_index]

    @property
    def is_playing(self) -> bool:
        if self._is_main_app_running():
            state = self.get_state()
            return bool(state.get("playing", False))
        if self._standalone_player is not None:
            return self._standalone_player.is_playing
        return False

    def toggle_play(self) -> None:
        if self._is_main_app_running():
            self._send_cmd("toggle")
        elif self._standalone_player is not None:
            self._standalone_player.toggle_play_pause()

    def next_track(self) -> None:
        if self._is_main_app_running():
            self._send_cmd("next")
        elif self._standalone_player is not None:
            self._standalone_player.next()

    def prev_track(self) -> None:
        if self._is_main_app_running():
            self._send_cmd("prev")
        elif self._standalone_player is not None:
            self._standalone_player.previous()

    def seek(self, position: float) -> None:
        """Seek to position in seconds."""
        if not self._is_main_app_running() and self._standalone_player is not None:
            self._standalone_player.seek(position)

    def set_volume(self, volume: float) -> None:
        """Set volume 0.0-1.0."""
        if not self._is_main_app_running() and self._standalone_player is not None:
            self._standalone_player.set_volume(volume)

    def volume_up(self) -> None:
        """Increase volume by 10%."""
        if self._is_main_app_running():
            self._send_cmd("volume_up")
        elif self._standalone_player is not None:
            new_vol = min(1.0, self._standalone_player.volume + 0.1)
            self._standalone_player.set_volume(new_vol)

    def volume_down(self) -> None:
        """Decrease volume by 10%."""
        if self._is_main_app_running():
            self._send_cmd("volume_down")
        elif self._standalone_player is not None:
            new_vol = max(0.0, self._standalone_player.volume - 0.1)
            self._standalone_player.set_volume(new_vol)

    def cycle_mode(self) -> None:
        if self._is_main_app_running():
            self._send_cmd("mode")
        self._mode_index = (self._mode_index + 1) % len(self._MODES)
        if not self._is_main_app_running() and self._standalone_player is not None:
            self._standalone_player.set_play_mode(self._MODES[self._mode_index])

    def get_state(self) -> dict:
        if self._state_file.exists():
            try:
                with open(self._state_file, "r", encoding="utf-8") as f:
                    self._cached_state = json.load(f)
            except Exception:
                pass
        return self._cached_state

    def load_playlist(self, songs: list) -> None:
        if not self._is_main_app_running():
            if self._standalone_player is None:
                self._standalone_player = Player()
            typed_songs = [s if isinstance(s, Song) else Song(**s) for s in songs]
            self._standalone_player.load_playlist(typed_songs)

    def _is_main_app_running(self) -> bool:
        if not self._state_file.exists():
            return False
        try:
            with open(self._state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            last_time = state.get("time", 0)
            return (time.time() - last_time) < 5.0
        except Exception:
            return False

    def _send_cmd(self, cmd: str) -> None:
        self._ipc_dir.mkdir(parents=True, exist_ok=True)
        payload = {"cmd": cmd, "time": int(time.time())}
        with open(self._cmd_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
