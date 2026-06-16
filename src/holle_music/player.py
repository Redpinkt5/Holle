"""音频播放引擎 — 基于 pygame.mixer 的播放控制."""

import time
from enum import Enum, auto
from pathlib import Path
from holle_music.models import Song
from holle_music.spectrum import SpectrumAnalyzer


class PlayerState(Enum):
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()


class Player:
    """音频播放器，封装 pygame.mixer.music.

    支持 play/pause/resume/stop/next/prev 操作。
    """

    def __init__(self) -> None:
        self._state = PlayerState.STOPPED
        self._volume = 1.0
        self._playlist: list[Song] = []
        self._current_index = 0
        self._initialized = False
        self._on_song_change_callbacks: list = []
        self._analyzer: SpectrumAnalyzer | None = None
        self._play_start: float = 0.0
        self._paused_at: float = 0.0
        self._play_mode: str = "sequential"
        self._resume_position: float = 0.0

    def set_play_mode(self, mode: str) -> None:
        self._play_mode = mode

    @property
    def play_mode(self) -> str:
        return self._play_mode

    def _ensure_init(self) -> None:
        if not self._initialized:
            import pygame  # lazy import to avoid forcing pygame init in tests
            pygame.mixer.init()
            pygame.mixer.music.set_volume(self._volume)
            self._initialized = True

    @property
    def state(self) -> PlayerState:
        return self._state

    @property
    def volume(self) -> float:
        return self._volume

    @property
    def current_song(self) -> Song | None:
        if 0 <= self._current_index < len(self._playlist):
            return self._playlist[self._current_index]
        return None

    @property
    def current_index(self) -> int:
        return self._current_index if self._playlist else 0

    @property
    def playlist(self) -> list[Song]:
        return list(self._playlist)

    @property
    def is_playing(self) -> bool:
        return self._state == PlayerState.PLAYING

    def on_song_change(self, callback):
        """注册歌曲切换回调."""
        self._on_song_change_callbacks.append(callback)

    def _notify_song_change(self) -> None:
        for cb in self._on_song_change_callbacks:
            try:
                cb(self.current_song)
            except Exception:
                pass

    def load_playlist(self, songs: list[Song]) -> bool:
        self._playlist = list(songs)
        self._current_index = 0 if songs else 0
        return True

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, volume))
        if self._initialized:
            import pygame
            pygame.mixer.music.set_volume(self._volume)

    def play(self, song: Song | None = None) -> None:
        self._ensure_init()
        import pygame

        if song is not None:
            if song not in self._playlist:
                self._playlist.insert(self._current_index + 1, song)
            self._current_index = self._playlist.index(song)

        if self.current_song is None:
            return

        path = str(self.current_song.path)

        if self._state == PlayerState.PAUSED:
            pygame.mixer.music.unpause()
            self._play_start = time.monotonic() - self._paused_at
            self._state = PlayerState.PLAYING
        else:
            if not Path(path).exists():
                return
            start_pos = self._resume_position
            self._resume_position = 0.0
            pygame.mixer.music.stop()
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(start=start_pos)
            pygame.mixer.music.set_volume(self._volume)
            self._play_start = time.monotonic() - start_pos
            self._state = PlayerState.PLAYING
            self._notify_song_change()
            # Load spectrum in background to avoid blocking playback
            import threading
            threading.Thread(target=self._load_spectrum, args=(path,), daemon=True).start()

    def _load_spectrum(self, path: str) -> None:
        """Load audio file into spectrum analyzer."""
        self._ensure_init()
        try:
            if self._analyzer is None:
                self._analyzer = SpectrumAnalyzer()
            self._analyzer.load(path)
        except Exception:
            self._analyzer = None

    def get_playback_position_ms(self) -> float:
        """Return current playback position in milliseconds (time-based)."""
        if self._state == PlayerState.PLAYING:
            return (time.monotonic() - self._play_start) * 1000.0
        elif self._state == PlayerState.PAUSED:
            return self._paused_at * 1000.0
        return 0.0

    def get_current_spectrum(self) -> list[float]:
        """Return current playback spectrum (24 bands, 0.0-1.0)."""
        if self._analyzer is None or not self._analyzer.is_loaded:
            return [0.0] * 24
        try:
            pos_ms = self.get_playback_position_ms()
            return self._analyzer.get_spectrum(float(pos_ms), self.is_playing)
        except Exception:
            return [0.0] * 24

    def has_ended(self) -> bool:
        """Check if the current song has finished playing."""
        if self._state != PlayerState.PLAYING:
            return False
        song = self.current_song
        if song is None:
            return False
        # Primary: if mixer reports not busy, audio definitely stopped
        import pygame
        if self._initialized and not pygame.mixer.music.get_busy():
            return True
        if song.duration <= 0:
            return False
        elapsed = self.get_playback_position_ms() / 1000.0
        return elapsed >= song.duration

    def pause(self) -> None:
        if self._state != PlayerState.PLAYING:
            return
        self._ensure_init()
        import pygame
        pygame.mixer.music.pause()
        self._paused_at = time.monotonic() - self._play_start
        self._state = PlayerState.PAUSED

    def seek(self, position_seconds: float) -> None:
        """Seek to position in seconds."""
        if not self._initialized:
            return
        import pygame
        try:
            pygame.mixer.music.set_pos(position_seconds)
        except Exception:
            pass
        self._play_start = time.monotonic() - position_seconds
        self._paused_at = position_seconds

    def set_resume_position(self, position: float) -> None:
        """Set the position to resume from the next time play() is called."""
        self._resume_position = max(0.0, position)

    def get_duration(self) -> float:
        """Return current song duration in seconds."""
        song = self.current_song
        if song is None:
            return 0.0
        return song.duration

    def stop(self) -> None:
        if self._initialized:
            import pygame
            pygame.mixer.music.stop()
        self._state = PlayerState.STOPPED
        self._play_start = 0.0
        self._paused_at = 0.0

    def toggle_play_pause(self) -> None:
        if self._state == PlayerState.PLAYING:
            self.pause()
        else:
            self.play()

    def next(self) -> None:
        if not self._playlist:
            return
        was_playing = self._state == PlayerState.PLAYING
        if was_playing:
            self._state = PlayerState.STOPPED
        if self._play_mode == "random":
            # Playlist already shuffled; just move to next in the shuffled order
            self._current_index = (self._current_index + 1) % len(self._playlist)
        elif self._play_mode == "repeat":
            # Stay on same song
            pass
        else:
            self._current_index = (self._current_index + 1) % len(self._playlist)
        if was_playing:
            self.play()
        else:
            # Notify even when paused so UI/state stays in sync.
            self._notify_song_change()

    def previous(self, restart_threshold_seconds: float = 5.0) -> None:
        if not self._playlist:
            return
        # If currently playing and within the first few seconds, restart the
        # current song instead of going back to the previous track.
        if (
            self._state == PlayerState.PLAYING
            and (time.monotonic() - self._play_start) >= restart_threshold_seconds
        ):
            self.play()
            return

        was_playing = self._state == PlayerState.PLAYING
        if was_playing:
            self._state = PlayerState.STOPPED
        self._current_index = (self._current_index - 1) % len(self._playlist)
        if was_playing:
            self.play()
        else:
            # Notify even when paused so UI/state stays in sync.
            self._notify_song_change()

    def cleanup(self) -> None:
        if self._initialized:
            import pygame
            pygame.mixer.music.stop()
            pygame.mixer.quit()
            self._initialized = False
