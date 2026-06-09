# Desktop Pet 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Holle Music ASCII 吉祥物做成 Windows 桌面宠物，支持点击控制播放、AI 对话、独立/联动双模式。

**Architecture:** pywin32 创建 WS_EX_LAYERED 无边框置顶透明窗口，Pillow 实时渲染吉祥物 PNG，IPC 通过 JSON 文件实现主程序与桌宠联动，tkinter 做 AI 对话浮窗。

**Tech Stack:** Python 3.10+, pywin32, Pillow, tkinter, pygame

---

## 文件结构

```
src/holle_music/
├── pet/
│   ├── __init__.py          # 包初始化，导出入口
│   ├── renderer.py          # MascotRenderer：ASCII → PNG
│   ├── window.py            # PetWindow：pywin32 窗口
│   ├── player_proxy.py      # PetPlayer：独立播放 / IPC 联动
│   ├── chat_dialog.py       # ChatDialog：tkinter 对话浮窗
│   └── main.py              # 桌宠入口
├── app.py                   # 主程序：增加 IPC 定时器
├── player.py                # 播放引擎（无改动）
├── minimax_api.py           # AI 服务（无改动）
└── widgets.py               # TUI 组件（复用 _BODY/_EYES）

tests/pet/
├── test_renderer.py         # 渲染器测试
├── test_click_zone.py       # 点击区域测试
└── test_player_proxy.py     # IPC 测试
```

---

### Task 1: MascotRenderer — 吉祥物渲染器

**Files:**
- Create: `src/holle_music/pet/__init__.py`
- Create: `src/holle_music/pet/renderer.py`
- Test: `tests/pet/test_renderer.py`

- [ ] **Step 1: 创建 pet 包**

```bash
mkdir -p src/holle_music/pet tests/pet
touch src/holle_music/pet/__init__.py
```

- [ ] **Step 2: 编写渲染器测试**

`tests/pet/test_renderer.py`:
```python
"""Tests for MascotRenderer."""

from pathlib import Path
from PIL import Image
from holle_music.pet.renderer import MascotRenderer


class TestMascotRenderer:
    def test_render_returns_image(self):
        r = MascotRenderer()
        img = r.render("center", active=False, shimmer_color="#ff69b4")
        assert isinstance(img, Image.Image)
        assert img.mode == "RGBA"
        assert img.width > 0
        assert img.height > 0

    def test_render_different_directions(self):
        r = MascotRenderer()
        for direction in ["center", "left", "right", "up", "down"]:
            img = r.render(direction, active=False, shimmer_color="#ff69b4")
            assert isinstance(img, Image.Image)

    def test_render_active_changes_appearance(self):
        r = MascotRenderer()
        img_off = r.render("center", active=False, shimmer_color="#ff69b4")
        img_on = r.render("center", active=True, shimmer_color="#ff69b4")
        # Active image should differ from inactive
        assert img_off.tobytes() != img_on.tobytes()

    def test_save_to_file(self, tmp_path: Path):
        r = MascotRenderer()
        img = r.render("center", active=False, shimmer_color="#ff69b4")
        path = tmp_path / "mascot.png"
        img.save(path)
        assert path.exists()
        assert path.stat().st_size > 0
```

- [ ] **Step 3: 运行测试，确认失败**

```bash
pytest tests/pet/test_renderer.py -v
```

Expected: 全部 FAIL — `MascotRenderer` 未定义

- [ ] **Step 4: 实现 MascotRenderer**

`src/holle_music/pet/renderer.py`:
```python
"""Desktop pet mascot renderer — ASCII art to transparent PNG."""

from __future__ import annotations

from holle_music.widgets import Mascot
from PIL import Image, ImageDraw


class MascotRenderer:
    """Render the Holle Music ASCII mascot as a transparent PNG image."""

    COLS: int = 14
    ROWS: int = 7
    CELL_SIZE: int = 14  # pixels per ASCII cell
    PADDING: int = 4

    # Colors
    BODY_COLOR: str = "#ff69b4"      # pink
    EYE_COLOR: str = "#ffffff"       # white
    PUPIL_COLOR: str = "#000000"     # black
    ACTIVE_GLOW: str = "#ff1493"     # deep pink

    # Reuse Mascot's body template
    _BODY: list[str] = Mascot._BODY
    _EYES: dict[str, tuple[tuple[int, int], tuple[int, int]]] = Mascot._EYES

    def render(
        self,
        direction: str,
        active: bool,
        shimmer_color: str = "#ff69b4",
    ) -> Image.Image:
        """Generate RGBA mascot image.

        Args:
            direction: Eye direction (center, left, right, up, down, etc.)
            active: Whether music is playing (adds glow effect)
            shimmer_color: Current shimmer color
        """
        width = self.COLS * self.CELL_SIZE + self.PADDING * 2
        height = self.ROWS * self.CELL_SIZE + self.PADDING * 2

        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        body_color = shimmer_color if active else self.BODY_COLOR

        self._draw_body(draw, body_color, active)
        self._draw_eyes(draw, direction)

        if active:
            self._draw_glow(draw, width, height, shimmer_color)

        return img

    def _draw_body(self, draw: ImageDraw.Draw, color: str, active: bool) -> None:
        """Draw diamond body from ASCII template."""
        for row_idx, row_str in enumerate(self._BODY):
            for col_idx, ch in enumerate(row_str):
                if ch == "█":
                    x1 = self.PADDING + col_idx * self.CELL_SIZE
                    y1 = self.PADDING + row_idx * self.CELL_SIZE
                    x2 = x1 + self.CELL_SIZE - 1
                    y2 = y1 + self.CELL_SIZE - 1
                    draw.rectangle([x1, y1, x2, y2], fill=color)

    def _draw_eyes(self, draw: ImageDraw.Draw, direction: str) -> None:
        """Draw eyes at position for given direction."""
        eye_pos = self._EYES.get(direction, self._EYES["center"])
        for (row, col) in eye_pos:
            x1 = self.PADDING + col * self.CELL_SIZE
            y1 = self.PADDING + row * self.CELL_SIZE
            x2 = x1 + self.CELL_SIZE - 1
            y2 = y1 + self.CELL_SIZE - 1
            # White eye
            draw.rectangle([x1, y1, x2, y2], fill=self.EYE_COLOR)
            # Black pupil (centered)
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            pr = self.CELL_SIZE // 4
            draw.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=self.PUPIL_COLOR)

    def _draw_glow(self, draw: ImageDraw.Draw, w: int, h: int, color: str) -> None:
        """Draw subtle glow border when playing."""
        # Simplified: draw a soft outer border
        glow_w = 2
        for i in range(glow_w):
            alpha = int(80 * (1 - i / glow_w))
            c = self._hex_to_rgba(color, alpha)
            draw.rectangle([i, i, w - 1 - i, h - 1 - i], outline=c)

    @staticmethod
    def _hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
        """Convert hex color to RGBA tuple."""
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b, alpha)
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
pytest tests/pet/test_renderer.py -v
```

Expected: 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/holle_music/pet/ tests/pet/
git commit -m "feat(pet): add MascotRenderer — ASCII to PNG"
```

---

### Task 2: ClickZone — 点击区域检测

**Files:**
- Create: `src/holle_music/pet/click_zone.py`
- Test: `tests/pet/test_click_zone.py`

- [ ] **Step 1: 编写测试**

`tests/pet/test_click_zone.py`:
```python
"""Tests for ClickZone."""

from holle_music.pet.click_zone import ClickZone


class TestClickZone:
    def test_center_click(self):
        cz = ClickZone()
        assert cz.detect(70, 70, 140, 140) == "center"

    def test_left_click(self):
        cz = ClickZone()
        assert cz.detect(10, 70, 140, 140) == "left"

    def test_right_click(self):
        cz = ClickZone()
        assert cz.detect(130, 70, 140, 140) == "right"

    def test_top_click(self):
        cz = ClickZone()
        assert cz.detect(70, 10, 140, 140) == "top"

    def test_bottom_click(self):
        cz = ClickZone()
        assert cz.detect(70, 130, 140, 140) == "bottom"

    def test_outside_returns_empty(self):
        cz = ClickZone()
        assert cz.detect(0, 0, 140, 140) == ""
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/pet/test_click_zone.py -v
```

Expected: 6 tests FAIL

- [ ] **Step 3: 实现 ClickZone**

`src/holle_music/pet/click_zone.py`:
```python
"""Click zone detection for desktop pet."""

from __future__ import annotations


class ClickZone:
    """Map click coordinates to action zones.

    Zones (normalized coordinates):
        top:    (0.0, 0.0) to (1.0, 0.2)  → cycle play mode
        left:   (0.0, 0.2) to (0.2, 0.8)  → previous track
        center: (0.2, 0.2) to (0.8, 0.8)  → toggle play/pause
        right:  (0.8, 0.2) to (1.0, 0.8)  → next track
        bottom: (0.2, 0.8) to (0.8, 1.0)  → open chat dialog
    """

    ZONES: dict[str, tuple[float, float, float, float]] = {
        "top":    (0.0, 0.0, 1.0, 0.2),
        "left":   (0.0, 0.2, 0.2, 0.8),
        "center": (0.2, 0.2, 0.8, 0.8),
        "right":  (0.8, 0.2, 1.0, 0.8),
        "bottom": (0.2, 0.8, 0.8, 1.0),
    }

    def detect(self, x: int, y: int, width: int, height: int) -> str:
        """Return zone name for click position, or empty string."""
        if width <= 0 or height <= 0:
            return ""
        nx = x / width
        ny = y / height
        for name, (x1, y1, x2, y2) in self.ZONES.items():
            if x1 <= nx < x2 and y1 <= ny < y2:
                return name
        return ""
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/pet/test_click_zone.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/holle_music/pet/click_zone.py tests/pet/test_click_zone.py
git commit -m "feat(pet): add ClickZone — click area detection"
```

---

### Task 3: PetPlayer — 独立播放 / IPC 联动

**Files:**
- Create: `src/holle_music/pet/player_proxy.py`
- Test: `tests/pet/test_player_proxy.py`
- Modify: `src/holle_music/player.py`（如有需要添加序列化方法）

- [ ] **Step 1: 编写测试**

`tests/pet/test_player_proxy.py`:
```python
"""Tests for PetPlayer / IPC."""

import json
import time
from pathlib import Path

from holle_music.pet.player_proxy import PetPlayer


class TestPetPlayerStandalone:
    def test_initial_state(self):
        p = PetPlayer()
        assert p.mode in ("sequential", "random", "repeat")

    def test_cycle_mode(self):
        p = PetPlayer()
        modes = []
        for _ in range(4):
            modes.append(p.mode)
            p.cycle_mode()
        # Should cycle through 3 modes and return
        assert modes[0] != modes[1] or modes[1] != modes[2]


class TestPetPlayerIPC:
    def test_write_cmd(self, tmp_path: Path, monkeypatch):
        cmd_file = tmp_path / "cmd.json"
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(PetPlayer, "CMD_FILE", cmd_file)
        monkeypatch.setattr(PetPlayer, "STATE_FILE", state_file)

        p = PetPlayer()
        p._standalone = False  # force linked mode
        p._send_cmd("toggle")

        assert cmd_file.exists()
        data = json.loads(cmd_file.read_text())
        assert data["cmd"] == "toggle"
        assert "time" in data

    def test_read_state(self, tmp_path: Path, monkeypatch):
        cmd_file = tmp_path / "cmd.json"
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(PetPlayer, "CMD_FILE", cmd_file)
        monkeypatch.setattr(PetPlayer, "STATE_FILE", state_file)

        state = {
            "playing": True,
            "song": {"title": "Test", "artist": "Artist"},
            "mode": "random",
            "time": time.time(),
        }
        state_file.write_text(json.dumps(state))

        p = PetPlayer()
        p._standalone = False
        result = p.get_state()
        assert result["playing"] is True
        assert result["song"]["title"] == "Test"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/pet/test_player_proxy.py -v
```

Expected: 4 tests FAIL

- [ ] **Step 3: 实现 PetPlayer**

`src/holle_music/pet/player_proxy.py`:
```python
"""Desktop pet player — standalone or linked to main app via IPC."""

from __future__ import annotations

import json
import time
from pathlib import Path


class PetPlayer:
    """Play music in standalone mode, or proxy to main app via IPC files.

    IPC Protocol:
        ~/.holle_music/pet_state.json  — main app writes current state
        ~/.holle_music/pet_cmd.json    — pet writes commands for main app
    """

    STATE_DIR = Path.home() / ".holle_music"
    STATE_FILE = STATE_DIR / "pet_state.json"
    CMD_FILE = STATE_DIR / "pet_cmd.json"

    _MODE_SEQUENCE = ["sequential", "random", "repeat"]

    def __init__(self) -> None:
        self._standalone = not self._is_main_app_running()
        self._player = None
        self._mode_idx = 0

        if self._standalone:
            from holle_music.player import Player
            self._player = Player()

        self.STATE_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def mode(self) -> str:
        if self._standalone and self._player:
            return self._player.play_mode or self._MODE_SEQUENCE[0]
        state = self.get_state()
        return state.get("mode", self._MODE_SEQUENCE[0])

    @property
    def is_playing(self) -> bool:
        if self._standalone and self._player:
            return self._player.is_playing
        state = self.get_state()
        return state.get("playing", False)

    def _is_main_app_running(self) -> bool:
        """Check if main app is active (state file updated in last 5s)."""
        try:
            if not self.STATE_FILE.exists():
                return False
            data = json.loads(self.STATE_FILE.read_text())
            last_update = data.get("time", 0)
            return (time.time() - last_update) < 5.0
        except Exception:
            return False

    def toggle_play(self) -> None:
        if self._standalone and self._player:
            self._player.toggle_play_pause()
        else:
            self._send_cmd("toggle")

    def next_track(self) -> None:
        if self._standalone and self._player:
            self._player.next()
        else:
            self._send_cmd("next")

    def prev_track(self) -> None:
        if self._standalone and self._player:
            self._player.previous()
        else:
            self._send_cmd("prev")

    def cycle_mode(self) -> None:
        if self._standalone and self._player:
            self._mode_idx = (self._mode_idx + 1) % len(self._MODE_SEQUENCE)
            mode = self._MODE_SEQUENCE[self._mode_idx]
            self._player.set_play_mode(mode)
        else:
            self._send_cmd("mode")

    def get_state(self) -> dict:
        """Read current playback state from IPC file or player."""
        if self._standalone and self._player:
            song = self._player.current_song
            return {
                "playing": self._player.is_playing,
                "song": {
                    "title": song.title if song else "",
                    "artist": song.artist if song else "",
                },
                "mode": self._player.play_mode,
                "time": time.time(),
            }
        try:
            if self.STATE_FILE.exists():
                return json.loads(self.STATE_FILE.read_text())
        except Exception:
            pass
        return {"playing": False, "song": {"title": "", "artist": ""}, "mode": "sequential"}

    def _send_cmd(self, cmd: str) -> None:
        """Write command to IPC file for main app to read."""
        try:
            self.CMD_FILE.write_text(
                json.dumps({"cmd": cmd, "time": time.time()}),
                encoding="utf-8",
            )
        except Exception:
            pass

    def load_playlist(self, songs: list) -> None:
        """Load songs in standalone mode."""
        if self._standalone and self._player:
            self._player.load_playlist(songs)
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/pet/test_player_proxy.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/holle_music/pet/player_proxy.py tests/pet/test_player_proxy.py
git commit -m "feat(pet): add PetPlayer with standalone and IPC linked mode"
```

---

### Task 4: PetWindow — pywin32 无边框置顶窗口

**Files:**
- Create: `src/holle_music/pet/window.py`
- Modify: `src/holle_music/pet/__init__.py`

- [ ] **Step 1: 实现 PetWindow**

`src/holle_music/pet/window.py`:
```python
"""Desktop pet window — layered, frameless, topmost, transparent."""

from __future__ import annotations

import math
import time
from typing import Callable

from holle_music.pet.click_zone import ClickZone
from holle_music.pet.renderer import MascotRenderer
from holle_music.widgets import Mascot as MascotWidget


class PetWindow:
    """Windows desktop pet window.

    Uses pywin32 to create a WS_EX_LAYERED window with transparent background.
    """

    def __init__(self, on_action: Callable[[str], None] | None = None) -> None:
        self._renderer = MascotRenderer()
        self._click_zone = ClickZone()
        self._on_action = on_action
        self._hwnd = 0
        self._dragging = False
        self._drag_start = (0, 0)
        self._window_pos = (100, 100)
        self._last_mouse = (0, 0)
        self._direction = "center"
        self._active = False
        self._shimmer_idx = 0
        self._shimmer_colors = [
            "#ff69b4", "#ffd700", "#ff4500", "#00bfff",
            "#9370db", "#32cd32", "#ffa500",
        ]
        self._running = True

    def show(self) -> None:
        """Create window and run message loop."""
        try:
            import win32api
            import win32con
            import win32gui
            import win32ui
        except ImportError:
            print("pywin32 not installed. Run: pip install pywin32")
            return

        self._hwnd = self._create_window()
        if not self._hwnd:
            return

        self._update_display()

        # Message loop with timer for animation
        msg = None
        while self._running:
            # Process messages
            if win32gui.PeekMessage(None, 0, 0, win32con.PM_REMOVE):
                win32gui.TranslateMessage(msg)
                win32gui.DispatchMessage(msg)
            else:
                # Update animation at ~30fps
                self._update_animation()
                time.sleep(1 / 30)

    def _create_window(self) -> int:
        """Create WS_EX_LAYERED window."""
        import win32con
        import win32gui

        wndclass = win32gui.WNDCLASS()
        wndclass.hInstance = win32gui.GetModuleHandle(None)
        wndclass.lpszClassName = "HollePetWindow"
        wndclass.lpfnWndProc = self._wnd_proc
        win32gui.RegisterClass(wndclass)

        img = self._renderer.render("center", False)
        w, h = img.size

        style = win32con.WS_POPUP
        ex_style = (
            win32con.WS_EX_LAYERED
            | win32con.WS_EX_TOOLWINDOW
            | win32con.WS_EX_TOPMOST
            | win32con.WS_EX_TRANSPARENT
        )

        hwnd = win32gui.CreateWindowEx(
            ex_style,
            wndclass.lpszClassName,
            "Holle Pet",
            style,
            self._window_pos[0],
            self._window_pos[1],
            w,
            h,
            0,
            0,
            wndclass.hInstance,
            None,
        )

        # Set transparency: black pixels are fully transparent
        win32gui.SetLayeredWindowAttributes(
            hwnd, 0x000000, 0, win32con.LWA_COLORKEY
        )

        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        win32gui.UpdateWindow(hwnd)

        return hwnd

    def _wnd_proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        """Window procedure."""
        import win32api
        import win32con
        import win32gui

        if msg == win32con.WM_LBUTTONDOWN:
            x = win32api.LOWORD(lparam)
            y = win32api.HIWORD(lparam)
            zone = self._click_zone.detect(x, y, *self._get_size())
            if zone:
                self._handle_click(zone)
            else:
                # Start drag
                self._dragging = True
                self._drag_start = win32api.GetCursorPos()
            return 0

        elif msg == win32con.WM_LBUTTONUP:
            self._dragging = False
            return 0

        elif msg == win32con.WM_MOUSEMOVE:
            if self._dragging:
                cx, cy = win32api.GetCursorPos()
                sx, sy = self._drag_start
                self._window_pos = (
                    self._window_pos[0] + cx - sx,
                    self._window_pos[1] + cy - sy,
                )
                self._drag_start = (cx, cy)
                win32gui.SetWindowPos(
                    hwnd, 0,
                    self._window_pos[0], self._window_pos[1],
                    0, 0,
                    win32con.SWP_NOSIZE | win32con.SWP_NOZORDER,
                )
            else:
                # Update eye direction
                x = win32api.LOWORD(lparam)
                y = win32api.HIWORD(lparam)
                self._update_eye_direction(x, y)
            return 0

        elif msg == win32con.WM_RBUTTONUP:
            # Context menu: hide, quit
            self._show_context_menu()
            return 0

        elif msg == win32con.WM_DESTROY:
            self._running = False
            win32gui.PostQuitMessage(0)
            return 0

        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _get_size(self) -> tuple[int, int]:
        """Get current window size."""
        img = self._renderer.render(self._direction, self._active)
        return img.size

    def _update_eye_direction(self, x: int, y: int) -> None:
        """Calculate eye direction based on mouse position."""
        w, h = self._get_size()
        cx, cy = w // 2, h // 2
        dx = x - cx
        dy = y - cy
        dist = math.hypot(dx, dy)
        if dist < 5:
            new_dir = "center"
        else:
            angle = math.degrees(math.atan2(dy, dx))
            # Map angle to direction (simplified)
            dirs = [
                (-22.5, 22.5, "right"),
                (22.5, 67.5, "bottom_right"),
                (67.5, 112.5, "down"),
                (112.5, 157.5, "bottom_left"),
                (157.5, 180, "left"),
                (-180, -157.5, "left"),
                (-157.5, -112.5, "top_left"),
                (-112.5, -67.5, "up"),
                (-67.5, -22.5, "top_right"),
            ]
            new_dir = "center"
            for lo, hi, d in dirs:
                if lo <= angle < hi:
                    new_dir = d
                    break

        if new_dir != self._direction:
            self._direction = new_dir
            self._update_display()

    def _update_animation(self) -> None:
        """Update shimmer animation."""
        if not self._active:
            return
        self._shimmer_idx = (self._shimmer_idx + 1) % len(self._shimmer_colors)
        self._update_display()

    def _update_display(self) -> None:
        """Render and update window content."""
        try:
            import win32api
            import win32con
            import win32gui
            import win32ui
        except ImportError:
            return

        color = self._shimmer_colors[self._shimmer_idx] if self._active else "#ff69b4"
        img = self._renderer.render(self._direction, self._active, color)

        # Convert PIL to HBITMAP and update layered window
        w, h = img.size
        hdc_screen = win32gui.GetDC(0)
        hdc_mem = win32ui.CreateDCFromHandle(hdc_screen)
        hdc_compatible = hdc_mem.CreateCompatibleDC()

        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(hdc_mem, w, h)
        hdc_compatible.SelectObject(bmp)

        # Draw image to bitmap
        img_bytes = img.tobytes("raw", "BGRA")
        bmp.SetBitmapBits(img_bytes)

        # Update layered window
        point_src = win32api.POINT(0, 0)
        size = win32api.SIZE(w, h)
        point_dst = win32api.POINT(self._window_pos[0], self._window_pos[1])
        blend = {
            "BlendOp": win32con.AC_SRC_OVER,
            "BlendFlags": 0,
            "SourceConstantAlpha": 255,
            "AlphaFormat": win32con.AC_SRC_ALPHA,
        }

        win32gui.UpdateLayeredWindow(
            self._hwnd, hdc_screen, point_dst, size,
            hdc_compatible.GetSafeHdc(), point_src, 0, blend, win32con.ULW_ALPHA,
        )

        hdc_compatible.DeleteDC()
        win32gui.ReleaseDC(0, hdc_screen)

    def _handle_click(self, zone: str) -> None:
        """Dispatch click action."""
        if self._on_action:
            self._on_action(zone)

    def _show_context_menu(self) -> None:
        """Show right-click context menu."""
        try:
            import win32api
            import win32con
            import win32gui

            menu = win32gui.CreatePopupMenu()
            win32gui.AppendMenu(menu, win32con.MF_STRING, 1, "Hide")
            win32gui.AppendMenu(menu, win32con.MF_STRING, 2, "Quit")

            x, y = win32api.GetCursorPos()
            cmd = win32gui.TrackPopupMenu(
                menu, win32con.TPM_RETURNCMD, x, y, 0, self._hwnd, None,
            )
            if cmd == 1:
                win32gui.ShowWindow(self._hwnd, win32con.SW_HIDE)
            elif cmd == 2:
                self._running = False
                win32gui.DestroyWindow(self._hwnd)
        except Exception:
            pass

    def set_active(self, active: bool) -> None:
        """Set playing state (triggers shimmer)."""
        if active != self._active:
            self._active = active
            self._update_display()
```

- [ ] **Step 2: 验证导入**

```bash
python -c "from holle_music.pet.window import PetWindow; print('OK')"
```

Expected: `OK`（pywin32 未安装时会打印提示但不报错）

- [ ] **Step 3: Commit**

```bash
git add src/holle_music/pet/window.py
git commit -m "feat(pet): add PetWindow — pywin32 layered topmost window"
```

---

### Task 5: 主程序 IPC 支持

**Files:**
- Modify: `src/holle_music/app.py`

- [ ] **Step 1: 在 app.py 中添加 IPC 定时器**

在 `app.py` 的 `HolleMusicApp` 类中，找到 `on_mount` 方法，在末尾添加：

```python
    def on_mount(self) -> None:
        """应用启动后初始化。"""
        # ... existing code ...
        
        # IPC for desktop pet
        self._pet_state_timer = self.set_interval(1.0, self._write_pet_state)
        self._pet_cmd_timer = self.set_interval(0.5, self._read_pet_cmd)
        
        # Ensure IPC directory exists
        from pathlib import Path
        (Path.home() / ".holle_music").mkdir(parents=True, exist_ok=True)
```

在 `app.py` 中添加两个新方法：

```python
    def _write_pet_state(self) -> None:
        """Write current playback state for desktop pet."""
        import json
        from pathlib import Path
        
        song = self.player.current_song
        state = {
            "playing": self.player.is_playing,
            "song": {
                "title": song.title if song else "",
                "artist": song.artist if song else "",
            },
            "mode": self.player.play_mode,
            "time": time.time(),
        }
        try:
            path = Path.home() / ".holle_music" / "pet_state.json"
            path.write_text(json.dumps(state), encoding="utf-8")
        except Exception:
            pass

    def _read_pet_cmd(self) -> None:
        """Read commands from desktop pet and execute."""
        import json
        from pathlib import Path
        
        cmd_file = Path.home() / ".holle_music" / "pet_cmd.json"
        if not cmd_file.exists():
            return
        
        try:
            data = json.loads(cmd_file.read_text(encoding="utf-8"))
            cmd = data.get("cmd", "")
            cmd_time = data.get("time", 0)
            
            # Only process commands from last 3 seconds
            if time.time() - cmd_time > 3:
                return
            
            if cmd == "toggle":
                self.player.toggle_play_pause()
                self._update_controls_ui()
            elif cmd == "next":
                self.player.next()
                self._sync_playlist_selection()
            elif cmd == "prev":
                self.player.previous()
                self._sync_playlist_selection()
            elif cmd == "mode":
                self._cycle_play_mode()
            
            # Delete after processing
            cmd_file.unlink()
        except Exception:
            pass
```

- [ ] **Step 2: 确认导入正常**

```bash
python -c "from holle_music.app import HolleMusicApp; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/holle_music/app.py
git commit -m "feat: add IPC support for desktop pet — state broadcast + command reading"
```

---

### Task 6: ChatDialog — AI 对话浮窗

**Files:**
- Create: `src/holle_music/pet/chat_dialog.py`

- [ ] **Step 1: 实现 ChatDialog**

`src/holle_music/pet/chat_dialog.py`:
```python
"""Floating chat dialog for desktop pet — tkinter."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from holle_music.minimax_api import MiniMaxService


class ChatDialog:
    """Floating chat dialog below the pet."""

    def __init__(self) -> None:
        self._window: tk.Toplevel | None = None
        self._service = MiniMaxService()
        self._messages: list[tuple[str, str]] = []  # [(role, text), ...]

    def show(self, x: int, y: int) -> None:
        """Show dialog at position (below pet)."""
        if self._window is not None and self._window.winfo_exists():
            self._window.lift()
            return

        self._window = tk.Toplevel()
        self._window.overrideredirect(True)
        self._window.attributes("-topmost", True)
        self._window.geometry(f"320x240+{x}+{y + 120}")
        self._window.configure(bg="#1e1e1e")

        # Click outside to close
        self._window.bind("<FocusOut>", lambda e: self.hide())
        self._window.bind("<Escape>", lambda e: self.hide())

        # Messages area
        self._canvas = tk.Canvas(
            self._window, bg="#1e1e1e", highlightthickness=0,
        )
        self._canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))

        scrollbar = ttk.Scrollbar(self._canvas, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._msg_frame = tk.Frame(self._canvas, bg="#1e1e1e")
        self._canvas.create_window((0, 0), window=self._msg_frame, anchor=tk.NW)

        # Input area
        input_frame = tk.Frame(self._window, bg="#1e1e1e")
        input_frame.pack(fill=tk.X, padx=8, pady=8)

        self._input = tk.Entry(
            input_frame,
            bg="#2d2d2d",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief=tk.FLAT,
            font=("Consolas", 10),
        )
        self._input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._input.bind("<Return>", lambda e: self._on_send())
        self._input.focus_set()

        send_btn = tk.Label(
            input_frame,
            text="➤",
            bg="#1e1e1e",
            fg="#ff69b4",
            font=("Consolas", 12),
            cursor="hand2",
        )
        send_btn.pack(side=tk.RIGHT, padx=(8, 0))
        send_btn.bind("<Button-1>", lambda e: self._on_send())

        self._redraw_messages()

    def hide(self) -> None:
        """Hide dialog."""
        if self._window is not None and self._window.winfo_exists():
            self._window.destroy()
            self._window = None

    def _on_send(self) -> None:
        """Send message to AI."""
        text = self._input.get().strip()
        if not text:
            return
        self._input.delete(0, tk.END)
        self._add_message("user", text)

        def _run():
            try:
                reply = self._service.chat(text)
                # Schedule UI update on main thread
                if self._window and self._window.winfo_exists():
                    self._window.after(0, lambda: self._add_message("ai", reply))
            except Exception as e:
                if self._window and self._window.winfo_exists():
                    self._window.after(0, lambda: self._add_message("ai", f"Error: {e}"))

        threading.Thread(target=_run, daemon=True).start()

    def _add_message(self, role: str, text: str) -> None:
        """Add message to list and redraw."""
        self._messages.append((role, text))
        # Keep last 20 messages
        self._messages = self._messages[-20:]
        self._redraw_messages()

    def _redraw_messages(self) -> None:
        """Redraw all message bubbles."""
        if self._window is None or not self._window.winfo_exists():
            return

        # Clear existing
        for widget in self._msg_frame.winfo_children():
            widget.destroy()

        for role, text in self._messages:
            is_user = role == "user"
            color = "#ff69b4" if is_user else "#3d3d3d"
            fg = "#ffffff"
            anchor = tk.E if is_user else tk.W

            bubble = tk.Frame(self._msg_frame, bg=color, padx=8, pady=4)
            bubble.pack(anchor=anchor, fill=tk.X, pady=2)

            label = tk.Label(
                bubble,
                text=text,
                bg=color,
                fg=fg,
                font=("Consolas", 9),
                wraplength=260,
                justify=tk.LEFT if not is_user else tk.RIGHT,
            )
            label.pack()
```

- [ ] **Step 2: 验证导入**

```bash
python -c "from holle_music.pet.chat_dialog import ChatDialog; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/holle_music/pet/chat_dialog.py
git commit -m "feat(pet): add ChatDialog — tkinter floating AI chat window"
```

---

### Task 7: Pet Entry Point + 入口脚本

**Files:**
- Create: `src/holle_music/pet/main.py`
- Modify: `src/holle_music/pet/__init__.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: 实现入口**

`src/holle_music/pet/main.py`:
```python
"""Desktop pet entry point."""

from __future__ import annotations

from pathlib import Path

from holle_music.pet.chat_dialog import ChatDialog
from holle_music.pet.player_proxy import PetPlayer
from holle_music.pet.window import PetWindow


def main() -> None:
    """Start the desktop pet."""
    player = PetPlayer()
    chat = ChatDialog()

    def on_action(zone: str) -> None:
        if zone == "center":
            player.toggle_play()
        elif zone == "left":
            player.prev_track()
        elif zone == "right":
            player.next_track()
        elif zone == "top":
            player.cycle_mode()
        elif zone == "bottom":
            # Get window position for dialog
            # For now, center on screen
            import win32api
            x = win32api.GetSystemMetrics(0) // 2 - 160
            y = win32api.GetSystemMetrics(1) // 2 - 120
            chat.show(x, y)

    window = PetWindow(on_action=on_action)
    
    print("Holle Pet started!")
    print("Click center: play/pause | left/right: prev/next")
    print("Click top: mode | bottom: chat | drag: move | right-click: menu")
    
    window.show()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 更新 __init__.py**

`src/holle_music/pet/__init__.py`:
```python
"""Holle Music Desktop Pet."""

from holle_music.pet.main import main

__all__ = ["main"]
```

- [ ] **Step 3: 添加 pyproject.toml 入口**

```toml
[project.scripts]
Holle = "holle_music.app:main"
HollePet = "holle_music.pet.main:main"
```

- [ ] **Step 4: Commit**

```bash
git add src/holle_music/pet/main.py src/holle_music/pet/__init__.py pyproject.toml
git commit -m "feat(pet): add HollePet entry point"
```

---

### Task 8: 测试与验证

- [ ] **Step 1: 渲染器输出验证**

```bash
cd E:/DDDESKKKK/holle_music
python -c "
from holle_music.pet.renderer import MascotRenderer
r = MascotRenderer()
img = r.render('center', active=True, shimmer_color='#ff69b4')
img.save('/tmp/mascot_test.png')
print('Image size:', img.size)
print('OK')
"
```

Expected: `Image size: (204, 106)`（约值）, `OK`

- [ ] **Step 2: 运行全部单元测试**

```bash
pytest tests/pet/ -v
```

Expected: 全部 PASS

- [ ] **Step 3: 安装到本地环境**

```bash
pip install -e .
```

- [ ] **Step 4: 测试桌宠入口**

```bash
HollePet
```

Expected: 窗口出现，显示粉色菱形吉祥物，眼睛跟随鼠标。

- [ ] **Step 5: 测试联动模式**

1. 终端 1: `Holle`（启动主程序，加载歌曲）
2. 终端 2: `HollePet`（启动桌宠）
3. 点击桌宠中间 → 主程序播放/暂停
4. 点击桌宠侧边 → 主程序切歌
5. 点击桌宠底部 → 弹出 AI 对话框

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "test(pet): verify desktop pet end-to-end"
```

---

## Self-Review

### Spec Coverage Check

| 设计需求 | 对应 Task | 状态 |
|---------|----------|------|
| 吉祥物渲染 | Task 1 | ✅ |
| 点击区域检测 | Task 2 | ✅ |
| 独立/联动播放 | Task 3 | ✅ |
| pywin32 窗口 | Task 4 | ✅ |
| 主程序 IPC | Task 5 | ✅ |
| AI 对话浮窗 | Task 6 | ✅ |
| 入口点 | Task 7 | ✅ |
| 测试 | Task 8 | ✅ |

### Placeholder Scan

- 无 TBD/TODO
- 无 "appropriate error handling" 等模糊描述
- 所有代码步骤包含完整实现

### Type Consistency

- `MascotRenderer.render()` 返回 `Image.Image` — 一致
- `ClickZone.detect()` 返回 `str` — 一致
- `PetPlayer` 方法名统一：`toggle_play`, `next_track`, `prev_track`, `cycle_mode` — 一致
- `PetWindow._on_action` callback 参数 `str`（zone name）— 一致
