"""PetPlayer — 桌面音乐助手播放控制器，支持独立播放或 IPC 代理到主程序."""

import json
import time
from pathlib import Path

from holle_music.models import Song
from holle_music.player import Player
from holle_music.settings import set_setting


class PetPlayer:
    """桌面音乐助手播放器。

    当主程序运行时，通过 IPC 文件（~/.holle_music/pet_state.json 和
    pet_cmd.json）与主程序通信；主程序未运行时，回退到独立播放模式。
    """

    _MODES = ["sequential", "random", "repeat"]

    def __init__(self) -> None:
        self._mode_index = 0
        self._standalone_player: Player | None = None
        self._cached_state: dict = {}
        self._original_songs: list = []
        self._last_sync_time: float = 0.0

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
    def volume(self) -> float:
        """Return current volume as 0.0-1.0."""
        if self._is_main_app_running():
            state = self.get_state()
            return state.get("volume", 100) / 100.0
        if self._standalone_player is not None:
            return self._standalone_player.volume
        return 1.0

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

    def check_auto_advance(self) -> None:
        """Advance to the next track when the standalone player reaches the end.

        This is used by the desktop pet's main loop; when the terminal is in
        control, the terminal handles auto-advance instead.
        """
        if self._is_main_app_running() or self._standalone_player is None:
            return
        try:
            if self._standalone_player.is_playing and self._standalone_player.has_ended():
                self.next_track()
        except Exception:
            pass

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
        """Increase volume by 2%."""
        if self._is_main_app_running():
            self._send_cmd("volume_up")
        elif self._standalone_player is not None:
            new_vol = min(1.0, self._standalone_player.volume + 0.02)
            self._standalone_player.set_volume(new_vol)

    def volume_down(self) -> None:
        """Decrease volume by 2%."""
        if self._is_main_app_running():
            self._send_cmd("volume_down")
        elif self._standalone_player is not None:
            new_vol = max(0.0, self._standalone_player.volume - 0.02)
            self._standalone_player.set_volume(new_vol)

    def cycle_mode(self) -> str:
        """Cycle to the next play mode, reshuffle/restore in standalone, return mode name."""
        # Sync local index with the actual current mode before cycling.
        _ = self.mode
        self._mode_index = (self._mode_index + 1) % len(self._MODES)
        new_mode = self._MODES[self._mode_index]

        if self._is_main_app_running():
            self._send_cmd("mode")
        elif self._standalone_player is not None:
            self._standalone_player.set_play_mode(new_mode)
            if new_mode == "random":
                import random

                songs = list(self._standalone_player.playlist)
                if songs:
                    cur_idx = self._standalone_player.current_index
                    current_song = songs.pop(cur_idx)
                    random.shuffle(songs)
                    songs.insert(0, current_song)
                    self._standalone_player.load_playlist(songs)
                    self._standalone_player._current_index = 0
            elif new_mode == "sequential":
                if self._original_songs:
                    cur_song = self._standalone_player.current_song
                    self._standalone_player.load_playlist(self._original_songs)
                    if cur_song:
                        try:
                            idx = self._original_songs.index(cur_song)
                            self._standalone_player._current_index = idx
                        except ValueError:
                            pass

        # Persist the chosen mode so it survives restarts.
        set_setting("play_mode", new_mode)
        return new_mode

    def set_play_mode(self, mode: str) -> None:
        """Set the play mode directly (used on startup from saved settings)."""
        if mode not in self._MODES:
            return
        self._mode_index = self._MODES.index(mode)
        if self._standalone_player is not None:
            self._standalone_player.set_play_mode(mode)
        set_setting("play_mode", mode)

    def play_song(self, song: dict) -> None:
        """Play a specific song, via IPC if the main app is running, else standalone."""
        if self._is_main_app_running():
            self._send_cmd(f"play:{json.dumps(song, ensure_ascii=False)}")
        elif self._standalone_player is not None:
            try:
                typed = Song(**song) if not isinstance(song, Song) else song
                self._standalone_player.play(typed)
            except Exception:
                pass

    def play_artist(self, artist: str) -> None:
        """Play all songs by an artist, via IPC if the main app is running, else standalone."""
        state = self.get_state()
        playlist = state.get("playlist", [])
        matches = [s for s in playlist if artist.lower() in (s.get("artist") or "").lower()]
        if not matches:
            return
        if self._is_main_app_running():
            self._send_cmd(f"play_artist:{artist}")
        elif self._standalone_player is not None:
            typed = [s if isinstance(s, Song) else Song(**s) for s in matches]
            self._standalone_player.load_playlist(typed)
            self._standalone_player.play(typed[0])

    def set_volume_pct(self, volume: int) -> None:
        """Set volume by percentage (0-100)."""
        if self._is_main_app_running():
            self._send_cmd(f"volume:{volume}")
        elif self._standalone_player is not None:
            self._standalone_player.set_volume(volume / 100.0)

    def set_mode(self, mode: str) -> None:
        """Set play mode by name, via IPC or standalone."""
        if mode not in self._MODES:
            return
        self._mode_index = self._MODES.index(mode)
        if self._is_main_app_running():
            self._send_cmd(f"mode:{mode}")
        elif self._standalone_player is not None:
            self._standalone_player.set_play_mode(mode)
        set_setting("play_mode", mode)

    def get_state(self) -> dict:
        if self._state_file.exists():
            try:
                with open(self._state_file, "r", encoding="utf-8") as f:
                    self._cached_state = json.load(f)
            except Exception:
                pass
        return self._cached_state

    def _sync_from_state(self) -> None:
        """Sync standalone player from IPC state when main app is running.

        This keeps the standalone playlist/index in line with the main app so
        that get_now_playing_info always returns a consistent current song and
        next-songs list, even across main-app/pet transitions.
        """
        if not self._is_main_app_running():
            return
        state = self.get_state()
        state_time = state.get("time", 0)
        if state_time <= self._last_sync_time:
            return
        playlist = state.get("playlist")
        if not playlist or self._standalone_player is None:
            return
        try:
            typed = [s if isinstance(s, Song) else Song(**s) for s in playlist]
            cur_idx = state.get("current_index", 0)
            mode = state.get("mode", "sequential")
            self._standalone_player.load_playlist(typed)
            self._standalone_player._current_index = cur_idx
            self._standalone_player.set_play_mode(mode)
            self._original_songs = list(typed)
            self._last_sync_time = state_time
        except Exception:
            pass

    def get_now_playing_info(self) -> tuple[dict | None, list[dict]]:
        """Return current song and up to 10 upcoming songs in playback order.

        Always derives the answer from the standalone player so the displayed
        current song and next songs are guaranteed to match. The standalone
        player is first synced from IPC state when the main app is running.
        """
        self._sync_from_state()

        if self._standalone_player is None:
            state = self.get_state()
            song = state.get("song")
            next_songs = state.get("next_songs", [])
            return song, next_songs

        song_obj = self._standalone_player.current_song
        song = {"title": song_obj.title, "artist": song_obj.artist, "path": str(song_obj.path)} if song_obj else None
        playlist = self._standalone_player.playlist
        cur_idx = self._standalone_player.current_index
        next_songs: list[dict] = []
        if playlist:
            for i in range(10):
                idx = (cur_idx + 1 + i) % len(playlist)
                s = playlist[idx]
                next_songs.append({"title": s.title, "artist": s.artist})
        return song, next_songs

    def load_playlist(self, songs: list) -> None:
        """Load the playlist into the player.

        Always keep a standalone player ready so the pet can keep working even
        after the terminal app exits. When the main app is running, playback
        commands are still forwarded to it; otherwise the standalone player
        takes over.
        """
        if self._standalone_player is None:
            self._standalone_player = Player()
        typed_songs = [s if isinstance(s, Song) else Song(**s) for s in songs]
        self._standalone_player.load_playlist(typed_songs)
        self._original_songs = list(typed_songs)

    def _is_main_app_running(self) -> bool:
        if not self._state_file.exists():
            return False
        try:
            with open(self._state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            last_time = state.get("time", 0)
            source = state.get("source", "terminal")
            if source != "terminal":
                return False
            return (time.time() - last_time) < 5.0
        except Exception:
            return False

    def write_state(self) -> None:
        """Write the standalone player's current state to pet_state.json.

        This is used when the desktop assistant is running on its own so that
        the terminal app can resume at the same song/position later.
        """
        if self._is_main_app_running() or self._standalone_player is None:
            return
        try:
            song_obj = self._standalone_player.current_song
            song = {"title": song_obj.title, "artist": song_obj.artist, "path": str(song_obj.path)} if song_obj else None
            playlist = self._standalone_player.playlist
            state = {
                "playing": self._standalone_player.is_playing,
                "song": song,
                "mode": self._standalone_player.play_mode,
                "volume": int(self._standalone_player.volume * 100),
                "current_index": self._standalone_player.current_index,
                "position": self._standalone_player.get_playback_position_ms() / 1000.0,
                "playlist": [
                    {"title": s.title, "artist": s.artist, "path": str(s.path)}
                    for s in playlist
                ],
                "source": "pet",
                "time": time.time(),
            }
            self._ipc_dir.mkdir(parents=True, exist_ok=True)
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False)
        except Exception:
            pass

    def _send_cmd(self, cmd: str) -> None:
        self._ipc_dir.mkdir(parents=True, exist_ok=True)
        payload = {"cmd": cmd, "time": int(time.time())}
        with open(self._cmd_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
