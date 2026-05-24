"""音频播放引擎 — 基于 pygame.mixer 的播放控制."""

from enum import Enum, auto
from pathlib import Path
from holle_music.models import Song


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
        self._spectrum_data: list[list[float]] = []
        self._spectrum_duration: float = 0.0

    def _ensure_init(self) -> None:
        if not self._initialized:
            import pygame  # lazy import to avoid forcing pygame init in tests
            pygame.mixer.init()
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
        else:
            if not Path(path).exists():
                return
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()

        self._state = PlayerState.PLAYING
        self._notify_song_change()
        self._load_spectrum(path)

    def _load_spectrum(self, path: str) -> None:
        """预计算音频频谱数据."""
        try:
            import numpy as np
            import librosa
            audio, sr = librosa.load(path, sr=22050, duration=120.0)
            if len(audio) < 2048:
                return

            chunk_size = 2048
            hop = max(1, (len(audio) - chunk_size) // 200)

            self._spectrum_data = []
            self._spectrum_duration = len(audio) / sr

            for i in range(0, len(audio) - chunk_size, hop):
                if len(self._spectrum_data) >= 200:
                    break
                chunk = audio[i:i + chunk_size]
                fft = np.abs(np.fft.rfft(chunk * np.hanning(chunk_size)))
                num_bands = 32
                band_edges = np.logspace(
                    0, np.log10(max(1, len(fft) - 1)), num_bands + 1
                ).astype(int)
                bands = [
                    float(np.mean(fft[band_edges[j]:band_edges[j + 1]]))
                    for j in range(num_bands)
                ]
                self._spectrum_data.append(bands)
        except ImportError:
            self._spectrum_data = []
        except Exception:
            self._spectrum_data = []

    def get_current_spectrum(self) -> list[float]:
        """返回当前播放位置的频谱数据 (32 个频段)."""
        if not self._spectrum_data or not self._initialized:
            return [0.0] * 32
        try:
            import pygame
            pos_ms = pygame.mixer.music.get_pos()
            if pos_ms < 0:
                return [0.0] * 32
            ratio = (pos_ms / 1000.0) / self._spectrum_duration if self._spectrum_duration > 0 else 0
            idx = min(int(ratio * len(self._spectrum_data)), len(self._spectrum_data) - 1)
            return self._spectrum_data[idx]
        except Exception:
            return [0.0] * 32

    def pause(self) -> None:
        if self._state != PlayerState.PLAYING:
            return
        self._ensure_init()
        import pygame
        pygame.mixer.music.pause()
        self._state = PlayerState.PAUSED

    def stop(self) -> None:
        if self._initialized:
            import pygame
            pygame.mixer.music.stop()
        self._state = PlayerState.STOPPED

    def toggle_play_pause(self) -> None:
        if self._state == PlayerState.PLAYING:
            self.pause()
        else:
            self.play()

    def next(self) -> None:
        if not self._playlist:
            return
        was_playing = self._state == PlayerState.PLAYING
        self._current_index = (self._current_index + 1) % len(self._playlist)
        if was_playing:
            self.play()

    def previous(self) -> None:
        if not self._playlist:
            return
        was_playing = self._state == PlayerState.PLAYING
        self._current_index = (self._current_index - 1) % len(self._playlist)
        if was_playing:
            self.play()

    def cleanup(self) -> None:
        if self._initialized:
            import pygame
            pygame.mixer.music.stop()
            pygame.mixer.quit()
            self._initialized = False
