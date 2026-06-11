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
from holle_music.pet.renderer import MascotRenderer, CELL_SIZE, PADDING
from holle_music.widgets import Mascot as MascotWidget


_SHIMMER_COLORS = [
    "#ff69b4",
    "#ffd700",
    "#ff4500",
    "#00bfff",
    "#9370db",
    "#32cd32",
    "#ffa500",
]


class PetWindow:
    """Windows desktop pet window using pywin32 with WS_EX_LAYERED transparent background."""

    def __init__(self, on_action: Callable[[str], None] | None = None) -> None:
        self._renderer = MascotRenderer()
        self._click_zone = ClickZone()
        self._on_action = on_action
        self._hwnd: int = 0
        self._dragging = False
        self._drag_start = (0, 0)
        self._window_pos = self._load_position()
        self._direction = "center"
        self._active = False
        self._shimmer_idx = 0
        self._running = True
        self._size = self._calc_size()

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

        # Message loop with timer for animation
        while self._running:
            if win32gui.PeekMessage(None, 0, 0, win32con.PM_REMOVE):
                msg = win32gui.GetMessage(None, 0, 0)
                if msg[0] == 0:
                    break
                win32gui.TranslateMessage(msg[1])
                win32gui.DispatchMessage(msg[1])
            else:
                self._update_animation()
                time.sleep(1 / 30)

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
        width = MascotWidget.COLS * CELL_SIZE + PADDING * 2
        height = MascotWidget.ROWS * CELL_SIZE + PADDING * 2
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
                sx, sy = self._drag_start
                self._window_pos = (
                    self._window_pos[0] + cx - sx,
                    self._window_pos[1] + cy - sy,
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
            zone = self._click_zone.detect(x, y, *self._size)
            if zone:
                self._handle_click(zone)
            else:
                self._dragging = True
                self._drag_start = win32api.GetCursorPos()
            return 0

        if msg == win32con.WM_LBUTTONUP:
            self._dragging = False
            return 0

        if msg == win32con.WM_RBUTTONUP:
            self._show_context_menu()
            return 0

        if msg == win32con.WM_DESTROY:
            self._running = False
            win32gui.PostQuitMessage(0)
            return 0

        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    # ── Eye direction ─────────────────────────────────────────────────────

    def _update_eye_direction(self, x: int, y: int) -> None:
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
        self._shimmer_idx = (self._shimmer_idx + 1) % len(_SHIMMER_COLORS)
        self._update_display()

    def _update_display(self) -> None:
        if not self._hwnd or win32gui is None:
            return

        color = _SHIMMER_COLORS[self._shimmer_idx] if self._active else "#ff69b4"
        img = self._renderer.render(self._direction, self._active, color)
        w, h = img.size

        hdc_screen = win32gui.GetDC(0)
        hdc_mem = win32ui.CreateDCFromHandle(hdc_screen)
        hdc_compatible = hdc_mem.CreateCompatibleDC()

        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(hdc_mem, w, h)
        hdc_compatible.SelectObject(bmp)

        # Convert PIL to DIB via ctypes CreateDIBSection
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

        # Use ctypes structures for UpdateLayeredWindow (avoids pywintypes trimming)
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
