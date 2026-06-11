"""Desktop pet window — layered, frameless, topmost, transparent."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Callable

try:
    import win32api
    import win32con
    import win32gui
    import win32ui
except ImportError:  # pragma: no cover
    win32api = None  # type: ignore[assignment]
    win32con = None  # type: ignore[assignment]
    win32gui = None  # type: ignore[assignment]
    win32ui = None  # type: ignore[assignment]

from holle_music.pet.click_zone import ClickZone
from holle_music.pet.renderer import MascotRenderer, CELL_W, CELL_H, PADDING
from holle_music.widgets import Mascot as MascotWidget
from holle_music.widgets import _SHIMMER_PALETTES, _SHIMMER_INTERVAL, _current_palette


class PetWindow:
    """Windows desktop pet window using pywin32 with WS_EX_LAYERED transparent background."""

    def __init__(
        self,
        on_action: Callable[[str], None] | None = None,
        dialog: object | None = None,
    ) -> None:
        self._renderer = MascotRenderer()
        self._click_zone = ClickZone()
        self._on_action = on_action
        self._dialog = dialog
        self._hwnd: int = 0
        self._dragging = False
        self._drag_start = (0, 0)
        self._drag_click_pos: tuple[int, int] | None = None
        self._drag_has_moved = False
        self._drag_start_time = 0.0
        self._window_pos = self._load_position()
        self._last_eye_update = 0.0
        self._direction = "center"
        self._active = False
        self._shimmer_idx = 0
        self._last_shimmer_update = 0.0
        self._running = True
        self._size = self._calc_size()
        self._on_player_state_check: Callable[[], bool] | None = None

    # ── Public API ────────────────────────────────────────────────────────

    def show(self) -> None:
        """Create window and run message loop."""
        if win32gui is None:
            print("pywin32 not installed. Run: pip install pywin32")
            return

        self._hwnd = self._create_window()
        if not self._hwnd:
            return

        self._update_display()

        # Message loop using ctypes PeekMessage for proper non-blocking behavior
        import ctypes
        from ctypes import wintypes

        class _MSG(ctypes.Structure):
            _fields_ = [
                ("hwnd", wintypes.HWND),
                ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM),
                ("lParam", wintypes.LPARAM),
                ("time", wintypes.DWORD),
                ("pt", wintypes.POINT),
            ]

        msg = _MSG()
        user32 = ctypes.windll.user32

        while self._running:
            # Process all pending messages
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                if msg.message == win32con.WM_QUIT:
                    self._running = False
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

            if not self._running:
                break

            # Track mouse globally (even outside window) for eye direction
            self._track_mouse_global()

            # Sync playing state for shimmer
            if self._on_player_state_check is not None:
                is_playing = self._on_player_state_check()
                if is_playing != self._active:
                    self.set_active(is_playing)

            # Update tkinter dialog if open
            if self._dialog is not None:
                try:
                    self._dialog.update()
                except Exception:
                    pass

            self._update_animation()
            time.sleep(0.016)  # ~60fps

        self._save_position()

    def set_active(self, active: bool) -> None:
        """Set playing state (triggers shimmer animation)."""
        if active != self._active:
            self._active = active
            self._update_display()

    def close(self) -> None:
        """Close the window and stop the message loop."""
        self._running = False
        if self._hwnd and win32gui is not None:
            win32gui.PostMessage(self._hwnd, win32con.WM_CLOSE, 0, 0)

    # ── Window creation ───────────────────────────────────────────────────

    def _calc_size(self) -> tuple[int, int]:
        width = MascotWidget.COLS * CELL_W + PADDING * 2
        height = MascotWidget.ROWS * CELL_H + PADDING * 2
        return width, height

    def _create_window(self) -> int:
        wndclass = win32gui.WNDCLASS()
        wndclass.hInstance = win32gui.GetModuleHandle(None)
        wndclass.lpszClassName = "HollePetWindow"
        wndclass.lpfnWndProc = self._wnd_proc
        win32gui.RegisterClass(wndclass)

        w, h = self._size

        style = win32con.WS_POPUP
        ex_style = (
            win32con.WS_EX_LAYERED
            | win32con.WS_EX_TOOLWINDOW
            | win32con.WS_EX_TOPMOST
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

        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        win32gui.UpdateWindow(hwnd)

        return hwnd

    # ── Window procedure ──────────────────────────────────────────────────

    def _wnd_proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if msg == win32con.WM_MOUSEMOVE:
            x = win32api.LOWORD(lparam)
            y = win32api.HIWORD(lparam)
            if self._dragging:
                cx, cy = win32api.GetCursorPos()
                dx = cx - self._drag_start[0]
                dy = cy - self._drag_start[1]
                if abs(dx) > 3 or abs(dy) > 3:
                    self._drag_has_moved = True
                self._window_pos = (
                    self._window_pos[0] + dx,
                    self._window_pos[1] + dy,
                )
                self._drag_start = (cx, cy)
                win32gui.SetWindowPos(
                    hwnd,
                    0,
                    self._window_pos[0],
                    self._window_pos[1],
                    0,
                    0,
                    win32con.SWP_NOSIZE | win32con.SWP_NOZORDER,
                )
            else:
                self._update_eye_direction(x, y)
            return 0

        if msg == win32con.WM_LBUTTONDOWN:
            x = win32api.LOWORD(lparam)
            y = win32api.HIWORD(lparam)
            self._dragging = True
            self._drag_has_moved = False
            self._drag_start = win32api.GetCursorPos()
            self._drag_click_pos = (x, y)
            self._drag_start_time = time.monotonic()
            return 0

        if msg == win32con.WM_LBUTTONUP:
            x = win32api.LOWORD(lparam)
            y = win32api.HIWORD(lparam)
            self._dragging = False
            press_duration = time.monotonic() - self._drag_start_time
            is_click = (not self._drag_has_moved) and (press_duration < 0.2)
            if is_click and self._drag_click_pos:
                zone = self._click_zone.detect(x, y, *self._size)
                if zone:
                    self._handle_click(zone)
            self._drag_has_moved = False
            return 0

        if msg == win32con.WM_RBUTTONUP:
            self._show_context_menu()
            return 0

        if msg == win32con.WM_TIMER:
            self._update_animation()
            return 0

        if msg == win32con.WM_DESTROY:
            self._running = False
            win32gui.KillTimer(hwnd, 1)
            win32gui.PostQuitMessage(0)
            return 0

        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _track_mouse_global(self) -> None:
        """Update eye direction based on global mouse position."""
        try:
            mx, my = win32api.GetCursorPos()
            rect = win32gui.GetWindowRect(self._hwnd)
            rel_x = mx - rect[0]
            rel_y = my - rect[1]
            self._update_eye_direction(rel_x, rel_y)
        except Exception:
            pass

    # ── Eye direction ─────────────────────────────────────────────────────

    def _update_eye_direction(self, x: int, y: int) -> None:
        # Throttle eye updates to ~10fps max (avoid lag on rapid mouse move)
        now = time.monotonic()
        if now - self._last_eye_update < 0.1:
            return
        self._last_eye_update = now

        w, h = self._size
        cx, cy = w // 2, h // 2
        dx = x - cx
        dy = y - cy
        if math.hypot(dx, dy) < 5:
            new_dir = "center"
        else:
            angle = math.degrees(math.atan2(dy, dx))
            new_dir = self._angle_to_direction(angle)

        if new_dir != self._direction:
            self._direction = new_dir
            self._update_display()

    @staticmethod
    def _angle_to_direction(angle: float) -> str:
        if -22.5 <= angle < 22.5:
            return "right"
        if 22.5 <= angle < 67.5:
            return "bottom_right"
        if 67.5 <= angle < 112.5:
            return "down"
        if 112.5 <= angle < 157.5:
            return "bottom_left"
        if angle >= 157.5 or angle < -157.5:
            return "left"
        if -157.5 <= angle < -112.5:
            return "top_left"
        if -112.5 <= angle < -67.5:
            return "up"
        return "top_right"

    # ── Animation & display ───────────────────────────────────────────────

    def _update_animation(self) -> None:
        if not self._active:
            return
        now = time.monotonic()
        if now - self._last_shimmer_update < _SHIMMER_INTERVAL:
            return
        self._last_shimmer_update = now
        palette = _SHIMMER_PALETTES[_current_palette]
        self._shimmer_idx = (self._shimmer_idx + 1) % len(palette)
        self._update_display()

    def _update_display(self) -> None:
        if not self._hwnd or win32gui is None:
            return

        img = self._renderer.render(self._direction, self._active, palette_name=_current_palette, shimmer_idx=self._shimmer_idx)
        w, h = img.size

        img_bytes = img.tobytes("raw", "BGRA")

        import ctypes
        from ctypes import wintypes

        gdi32 = ctypes.windll.gdi32

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", wintypes.DWORD),
                ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD),
            ]

        class RGBQUAD(ctypes.Structure):
            _fields_ = [
                ("rgbBlue", wintypes.BYTE),
                ("rgbGreen", wintypes.BYTE),
                ("rgbRed", wintypes.BYTE),
                ("rgbReserved", wintypes.BYTE),
            ]

        class BITMAPINFO(ctypes.Structure):
            _fields_ = [
                ("bmiHeader", BITMAPINFOHEADER),
                ("bmiColors", RGBQUAD * 1),
            ]

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h  # negative = top-down
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0  # BI_RGB

        hdc_screen = win32gui.GetDC(0)
        hdc_mem = win32gui.CreateCompatibleDC(hdc_screen)

        ppvBits = ctypes.c_void_p()
        hbmp = gdi32.CreateDIBSection(
            hdc_screen,
            ctypes.byref(bmi),
            0,  # DIB_RGB_COLORS
            ctypes.byref(ppvBits),
            None,
            0,
        )

        if hbmp and ppvBits.value:
            ctypes.memmove(ppvBits.value, img_bytes, len(img_bytes))

        old_bmp = win32gui.SelectObject(hdc_mem, hbmp)

        # ctypes structures for UpdateLayeredWindow (avoids pywintypes trimming)
        class _POINT(ctypes.Structure):
            _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

        class _SIZE(ctypes.Structure):
            _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]

        class _BLENDFUNCTION(ctypes.Structure):
            _fields_ = [
                ("BlendOp", wintypes.BYTE),
                ("BlendFlags", wintypes.BYTE),
                ("SourceConstantAlpha", wintypes.BYTE),
                ("AlphaFormat", wintypes.BYTE),
            ]

        pt_src = _POINT(0, 0)
        sz = _SIZE(w, h)
        pt_dst = _POINT(self._window_pos[0], self._window_pos[1])
        blend = _BLENDFUNCTION()
        blend.BlendOp = win32con.AC_SRC_OVER
        blend.BlendFlags = 0
        blend.SourceConstantAlpha = 255
        blend.AlphaFormat = win32con.AC_SRC_ALPHA

        user32 = ctypes.windll.user32
        user32.UpdateLayeredWindow(
            self._hwnd,
            hdc_screen,
            ctypes.byref(pt_dst),
            ctypes.byref(sz),
            hdc_mem,
            ctypes.byref(pt_src),
            0,
            ctypes.byref(blend),
            win32con.ULW_ALPHA,
        )

        win32gui.SelectObject(hdc_mem, old_bmp)
        win32gui.DeleteObject(hbmp)
        win32gui.DeleteDC(hdc_mem)
        win32gui.ReleaseDC(0, hdc_screen)

    # ── Click handling ────────────────────────────────────────────────────

    def _handle_click(self, zone: str) -> None:
        if self._on_action:
            self._on_action(zone)

    # ── Context menu ──────────────────────────────────────────────────────

    def _show_context_menu(self) -> None:
        try:
            menu = win32gui.CreatePopupMenu()
            win32gui.AppendMenu(menu, win32con.MF_STRING, 1, "Hide")
            win32gui.AppendMenu(menu, win32con.MF_STRING, 2, "Quit")

            x, y = win32api.GetCursorPos()
            cmd = win32gui.TrackPopupMenu(
                menu,
                win32con.TPM_RETURNCMD,
                x,
                y,
                0,
                self._hwnd,
                None,
            )
            if cmd == 1:
                win32gui.ShowWindow(self._hwnd, win32con.SW_HIDE)
            elif cmd == 2:
                self._running = False
                win32gui.DestroyWindow(self._hwnd)
        except Exception:
            pass

    # ── Position persistence ──────────────────────────────────────────────

    def _position_file(self) -> Path:
        return Path.home() / ".holle_music" / "pet_pos.json"

    def _load_position(self) -> tuple[int, int]:
        path = self._position_file()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return int(data.get("x", 100)), int(data.get("y", 100))
            except Exception:
                pass
        return 100, 100

    def _save_position(self) -> None:
        path = self._position_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(
                json.dumps({"x": self._window_pos[0], "y": self._window_pos[1]}),
                encoding="utf-8",
            )
        except Exception:
            pass
