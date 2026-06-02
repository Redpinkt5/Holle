"""Real-time audio spectrum analyzer.

Uses pygame.mixer.Sound + pygame.sndarray.array() for PCM extraction,
numpy.fft.rfft() for FFT, with Hanning window, dB conversion,
log-spaced frequency bands, frequency-dependent weighting,
adaptive normalization, soft compression, and natural decay.
"""

import math
import numpy as np


class SpectrumAnalyzer:
    """Real-time FFT spectrum analyzer for audio visualization.

    Loads audio via pygame.mixer.Sound, extracts mono PCM data,
    and provides per-frame frequency band magnitudes (0.0-1.0).
    """

    MAX_HEIGHT_RATIO: float = 0.70
    PEAK_EMA: float = 0.95          # global peak smoothing
    DYNAMIC_RANGE: float = 60.0     # dB range for normalization

    def __init__(self, num_bands: int = 24, sample_window: int = 4096) -> None:
        self._num_bands = num_bands
        self._sample_window = sample_window
        self._pcm: np.ndarray | None = None
        self._sample_rate: int = 44100
        self._smoothed: list[float] = []
        self._alpha: float = 0.65
        self._decay_rate: float = 0.988
        self._epsilon: float = 1e-10
        self._band_edges: np.ndarray | None = None
        self._band_gains: np.ndarray | None = None
        self._peak_db: float = -30.0

    def load(self, path: str) -> None:
        """Load audio file, extract mono PCM data and sample rate.

        Tries soundfile first (no pygame mixer interference), falls back
        to pygame.mixer.Sound for formats soundfile can't handle.
        """
        import pygame

        pcm = None
        sample_rate = 44100

        # Primary: soundfile (avoids interfering with pygame.mixer.music)
        try:
            import soundfile as sf
            data, sample_rate = sf.read(path, dtype='float32')
            if data.ndim == 2:
                pcm = data.mean(axis=1).astype(np.float32)
            else:
                pcm = data.astype(np.float32)
        except Exception:
            # Fallback: pygame.mixer.Sound + sndarray
            try:
                sound = pygame.mixer.Sound(path)
                raw = pygame.sndarray.array(sound)
                if raw.ndim == 2:
                    mono = raw.astype(np.float32).mean(axis=1)
                else:
                    mono = raw.astype(np.float32)
                if np.issubdtype(raw.dtype, np.integer):
                    mono /= float(np.iinfo(raw.dtype).max)
                pcm = mono
                # Get sample rate from soundfile info if possible
                try:
                    import soundfile as sf2
                    sample_rate = sf2.info(path).samplerate
                except Exception:
                    pass
            except Exception:
                pass

        if pcm is None or len(pcm) < 64:
            self._pcm = None
            return

        self._pcm = pcm
        self._sample_rate = sample_rate
        self._smoothed = [0.05] * self._num_bands
        self._peak_db = -30.0

        # Precompute log-spaced band edges (60Hz - 20kHz)
        # Start at 60Hz to skip sub-bass region with no musical content
        nyquist = self._sample_rate / 2
        max_freq = min(20000, nyquist)
        self._band_edges = np.logspace(
            math.log10(60), math.log10(max_freq), self._num_bands + 1
        )

        # Precompute per-band frequency gains (dB) — gentle high-freq compensation
        centers = np.sqrt(self._band_edges[:-1] * self._band_edges[1:])
        self._band_gains = np.zeros(self._num_bands, dtype=np.float32)
        self._band_gains[(centers >= 2000) & (centers < 5000)] = 1.5
        self._band_gains[(centers >= 5000) & (centers < 10000)] = 3.0
        self._band_gains[centers >= 10000] = 4.5

    def get_spectrum(self, position_ms: float, is_playing: bool) -> list[float]:
        """Return num_bands frequency magnitudes for current playback position."""
        if self._pcm is None or len(self._pcm) < 64:
            if is_playing:
                return list(self._smoothed)
            return self._apply_decay()

        # Map position to sample index — clamp to valid PCM range
        sample_idx = int(position_ms / 1000.0 * self._sample_rate)
        half = self._sample_window // 2
        max_idx = len(self._pcm) - self._sample_window
        if sample_idx > max_idx:
            sample_idx = max(max_idx, 0)
        start = max(0, sample_idx - half)
        end = min(len(self._pcm), start + self._sample_window)

        if end - start < 64:
            if is_playing:
                return list(self._smoothed)
            return self._apply_decay()

        # Extract windowed chunk
        chunk = self._pcm[start:end].copy()
        if len(chunk) < self._sample_window:
            padded = np.zeros(self._sample_window, dtype=np.float32)
            padded[:len(chunk)] = chunk
            chunk = padded

        # Hanning window + FFT
        window = np.hanning(len(chunk))
        fft = np.abs(np.fft.rfft(chunk * window))

        # Map FFT bins to log-spaced frequency bands, compute dB per band
        freqs = np.fft.rfftfreq(len(chunk), 1.0 / self._sample_rate)
        raw_db = np.zeros(self._num_bands, dtype=np.float32)
        for j in range(self._num_bands):
            lo, hi = self._band_edges[j], self._band_edges[j + 1]
            mask = (freqs >= lo) & (freqs < hi)
            if mask.any():
                raw_db[j] = float(np.max(fft[mask]))
            else:
                raw_db[j] = self._epsilon

        # Convert to dB and apply frequency weighting
        raw_db = 20 * np.log10(raw_db + self._epsilon)
        raw_db += self._band_gains

        # Global peak tracking (EMA) — preserves spectral shape
        frame_max = float(np.max(raw_db))
        self._peak_db = self._peak_db * self.PEAK_EMA + frame_max * (1.0 - self.PEAK_EMA)

        # Normalization with headroom: peak sits at MAX_HEIGHT_RATIO
        floor = self._peak_db - self.DYNAMIC_RANGE
        if self._peak_db <= floor:
            raw_bands = [0.0] * self._num_bands
        else:
            normalized = np.clip(
                (raw_db - floor) / self.DYNAMIC_RANGE, 0.0, 1.0
            ) * self.MAX_HEIGHT_RATIO
            raw_bands = list(normalized)

        # Moving average smoothing
        if len(self._smoothed) != self._num_bands:
            self._smoothed = raw_bands
        else:
            self._smoothed = [
                self._smoothed[i] * self._alpha + raw_bands[i] * (1 - self._alpha)
                for i in range(self._num_bands)
            ]

        return list(self._smoothed)

    def _apply_decay(self) -> list[float]:
        """Apply natural decay to smoothed values (30% max height per second)."""
        self._smoothed = [v * self._decay_rate for v in self._smoothed]
        return list(self._smoothed)

    def is_exhausted(self, position_ms: float) -> bool:
        """Check if the given position is past the available PCM data."""
        if self._pcm is None:
            return False
        sample_idx = int(position_ms / 1000.0 * self._sample_rate)
        half = self._sample_window // 2
        start = max(0, sample_idx - half)
        end = min(len(self._pcm), start + self._sample_window)
        return (end - start) < 64

    def reset(self) -> None:
        """Reset smoothing and peak tracking."""
        self._smoothed = [0.05] * self._num_bands
        self._peak_db = -30.0

    @property
    def num_bands(self) -> int:
        return self._num_bands

    @property
    def is_loaded(self) -> bool:
        return self._pcm is not None
