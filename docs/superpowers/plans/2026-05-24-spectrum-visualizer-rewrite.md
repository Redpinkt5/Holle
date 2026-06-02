# Spectrum Visualizer Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite audio spectrum visualizer with real-time FFT analysis (pygame.mixer.Sound + sndarray), 24 log-spaced frequency bands, dB scaling, moving average smoothing, natural decay, and 30fps rendering.

**Architecture:** New standalone `SpectrumAnalyzer` class in `spectrum.py` handles all audio analysis (load PCM, windowed FFT, dB conversion, log-band mapping, smoothing, decay). `Visualizer` widget renders 24 "█" bars at 30fps. `Player` creates analyzer on song load and delegates spectrum queries.

**Tech Stack:** pygame (mixer.Sound + sndarray), numpy (fft, hanning, logspace), soundfile (sample rate)

---

### Task 1: Create SpectrumAnalyzer class

**Files:**
- Create: `src/holle_music/spectrum.py`

- [ ] **Step 1: Write the SpectrumAnalyzer class**

```python
"""Real-time audio spectrum analyzer.

Uses pygame.mixer.Sound + pygame.sndarray.array() for PCM extraction,
numpy.fft.rfft() for FFT, with Hanning window, dB conversion,
log-spaced frequency bands, moving average smoothing, and natural decay.
"""

import math
import numpy as np


class SpectrumAnalyzer:
    """Real-time FFT spectrum analyzer for audio visualization.

    Loads audio via pygame.mixer.Sound, extracts mono PCM data,
    and provides per-frame frequency band magnitudes (0.0-1.0).
    """

    def __init__(self, num_bands: int = 24, sample_window: int = 1024) -> None:
        self._num_bands = num_bands
        self._sample_window = sample_window
        self._pcm: np.ndarray | None = None
        self._sample_rate: int = 44100
        self._smoothed: list[float] = []
        self._alpha: float = 0.7
        self._decay_rate: float = 0.85
        self._epsilon: float = 1e-10
        self._band_edges: np.ndarray | None = None

    def load(self, path: str) -> None:
        """Load audio file, extract mono PCM data and sample rate."""
        import pygame

        # Get sample rate via soundfile (lightweight, no decode overhead)
        try:
            import soundfile as sf
            info = sf.info(path)
            self._sample_rate = info.samplerate
        except Exception:
            self._sample_rate = 44100

        # Load PCM via pygame
        sound = pygame.mixer.Sound(path)
        raw = pygame.sndarray.array(sound)
        if raw.ndim == 2:
            mono = raw.astype(np.float32).mean(axis=1)
        else:
            mono = raw.astype(np.float32)

        self._pcm = mono
        self._smoothed = [0.05] * self._num_bands  # baseline

        # Precompute log-spaced band edges (20Hz - 20kHz)
        nyquist = self._sample_rate / 2
        max_freq = min(20000, nyquist)
        self._band_edges = np.logspace(
            math.log10(20), math.log10(max_freq), self._num_bands + 1
        )

    def get_spectrum(self, position_ms: float, is_playing: bool) -> list[float]:
        """Return num_bands frequency magnitudes for current playback position.

        Args:
            position_ms: Current playback position in milliseconds.
            is_playing: Whether audio is actively playing (vs paused/stopped).

        Returns:
            List of float values in [0.0, 1.0], one per frequency band.
        """
        if self._pcm is None or len(self._pcm) < 64:
            if is_playing:
                return list(self._smoothed)
            return self._apply_decay()

        # Map position to sample index
        sample_idx = int(position_ms / 1000.0 * self._sample_rate)
        half = self._sample_window // 2
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

        # Magnitude to dB, normalize to 0-1 (range: -60dB to 0dB)
        fft_db = 20 * np.log10(fft + self._epsilon)
        fft_db = np.clip(fft_db, -60, 0)
        fft_norm = (fft_db + 60) / 60

        # Map to log-spaced frequency bands
        freqs = np.fft.rfftfreq(len(chunk), 1.0 / self._sample_rate)
        raw_bands = []
        for j in range(self._num_bands):
            lo, hi = self._band_edges[j], self._band_edges[j + 1]
            mask = (freqs >= lo) & (freqs < hi)
            if mask.any():
                raw_bands.append(float(np.max(fft_norm[mask])))
            else:
                raw_bands.append(0.0)

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
        """Apply natural decay to smoothed values (when paused/stopped)."""
        self._smoothed = [v * self._decay_rate for v in self._smoothed]
        return list(self._smoothed)

    def reset(self) -> None:
        """Reset smoothing state to baseline."""
        self._smoothed = [0.05] * self._num_bands

    @property
    def num_bands(self) -> int:
        return self._num_bands

    @property
    def is_loaded(self) -> bool:
        return self._pcm is not None
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "from holle_music.spectrum import SpectrumAnalyzer; a = SpectrumAnalyzer(); print('OK:', a.num_bands, 'bands')"`
Expected: `OK: 24 bands`

- [ ] **Step 3: Commit**

```bash
git add src/holle_music/spectrum.py
git commit -m "feat: add SpectrumAnalyzer for real-time FFT audio analysis"
```

---

### Task 2: Rewrite Visualizer widget (24 bars, 30fps, █ render)

**Files:**
- Modify: `src/holle_music/widgets.py:112-182`

- [ ] **Step 1: Replace Visualizer class**

Replace the entire `Visualizer` class (lines 112-182) with:

```python
class Visualizer(Static):
    """歌曲律动面板 — 24 条 ASCII 频谱可视化，追随真实音频频率."""

    BORDER_TITLE = "歌曲律动"

    _bars: int = 24
    _timer_handle: object | None = None
    _get_spectrum: object = None  # callable → list[float] (24 values)

    def compose(self) -> ComposeResult:
        yield Static("", id="viz-content")

    def on_mount(self) -> None:
        self.styles.border = ("solid", "white")
        self.styles.content_align = ("center", "middle")
        self.styles.padding = 0

    def set_spectrum_source(self, source) -> None:
        """设置频谱数据源 (callable, 返回 24 个频段值)."""
        self._get_spectrum = source

    def start(self) -> None:
        """启动 30fps 频谱动画定时器."""
        self._timer_handle = self.set_interval(0.033, self._update_bars)

    def stop(self) -> None:
        """停止频谱动画."""
        if self._timer_handle is not None:
            self._timer_handle.stop()
            self._timer_handle = None
        content = self.query_one("#viz-content", Static)
        content.update("")

    def _render_bars(self, values: list[float]) -> str:
        """将 24 个频段值渲染为竖向 █ 条形图."""
        import math

        if not values:
            return ""

        clean = [v for v in values if not math.isnan(v)]
        if not clean:
            return ""

        # 可用高度 = 面板高度 - 边框(2行), 取 90%
        available = max(1, self.size.height - 2)
        max_height = max(1, int(available * 0.9))

        lines = []
        for level in range(max_height, 0, -1):
            row = ""
            for v in values:
                bar_h = int((0.0 if math.isnan(v) else v) * max_height)
                row += "█" if bar_h >= level else " "
            lines.append(row)
        return "\n".join(lines)

    def _update_bars(self) -> None:
        """从数据源获取频谱并更新显示."""
        if self._get_spectrum is not None:
            try:
                values = self._get_spectrum()
            except Exception:
                values = [0.05] * self._bars
        else:
            values = [0.05] * self._bars
        content = self.query_one("#viz-content", Static)
        content.update(self._render_bars(values))

    def set_active(self, active: bool) -> None:
        """设置为活跃/非活跃状态."""
        if active:
            self.start()
        else:
            self.stop()
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "from holle_music.widgets import Visualizer; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/holle_music/widgets.py
git commit -m "feat: rewrite Visualizer with 24 bars, 30fps, block-char rendering"
```

---

### Task 3: Integrate SpectrumAnalyzer into Player

**Files:**
- Modify: `src/holle_music/player.py:26-28,108-157`

- [ ] **Step 1: Add analyzer import and replace spectrum methods**

In `player.py`:

Add import at top:
```python
from holle_music.spectrum import SpectrumAnalyzer
```

Replace `__init__` spectrum fields (lines 27-28):
```python
        self._spectrum_data: list[list[float]] = []
        self._spectrum_duration: float = 0.0
```
→
```python
        self._analyzer: SpectrumAnalyzer | None = None
```

Replace `_load_spectrum` method (lines 110-142):
```python
    def _load_spectrum(self, path: str) -> None:
        """Load audio file into spectrum analyzer."""
        self._ensure_init()
        try:
            if self._analyzer is None:
                self._analyzer = SpectrumAnalyzer()
            self._analyzer.load(path)
        except Exception:
            self._analyzer = None
```

Replace `get_current_spectrum` method (lines 144-157):
```python
    def get_current_spectrum(self) -> list[float]:
        """Return current playback spectrum (24 bands, 0.0-1.0)."""
        if self._analyzer is None or not self._analyzer.is_loaded:
            return [0.05] * 24
        try:
            import pygame
            pos_ms = pygame.mixer.music.get_pos()
            if pos_ms < 0:
                pos_ms = 0
            return self._analyzer.get_spectrum(float(pos_ms), self.is_playing)
        except Exception:
            return [0.05] * 24
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "from holle_music.player import Player; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/holle_music/player.py
git commit -m "feat: integrate SpectrumAnalyzer into Player"
```

---

### Task 4: End-to-end smoke test

- [ ] **Step 1: Run the app and verify no import errors**

Run: `python -m holle_music 2>&1 | head -5`
Expected: App launches, no Traceback

- [ ] **Step 2: Check that the visualizer shows static baseline when no music is playing**

Manual: Observe the visualizer panel shows a low baseline (0.05 * 90% height ≈ 0).

- [ ] **Step 3: Commit any final adjustments**

```bash
git add -A
git commit -m "chore: final adjustments for spectrum visualizer rewrite"
```
