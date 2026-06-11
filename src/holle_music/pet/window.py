"""Desktop pet window — layered, frameless, topmost, transparent."""

from __future__ import annotations

import json
import math
import subprocess
import sys
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

from holle_music.pet.bubble import BubbleManager
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
        self._last_state_check = 0.0
        self._running = True
        self._size = self._calc_size()
        self._on_player_state_check: Callable[[], bool] | None = None
        self._bubble = BubbleManager(0, on_action=on_action)

    # ── Public API ────────────────────────────────────────────────────────

    def show(self) -> None:
        """Create window and run message loop."""
        if win32gui is None:
            print("[PET] pywin32 not installed")
            return

        self._hwnd = self._create_window()
        if not self._hwnd:
            print("[PET] Failed to create window")
            return

        print(f"[PET] Window created: hwnd={self._hwnd}")
        self._bubble._parent_hwnd = self._hwnd
        self._update_display()
        print("[PET] Entering message loop")

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
        frame = 0

        while self._running:
            frame += 1
            # Process all pending messages
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                if msg.message == win32con.WM_QUIT:
                    print("[PET] WM_QUIT received")
                    self._running = False
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

            if not self._running:
                break

            # Track mouse globally (even outside window) for eye direction
            self._track_mouse_global()

            # Sync playing state for shimmer (throttle to 0.5s)
            now = time.monotonic()
            if self._on_player_state_check is not None and now - self._last_state_check >= 0.5:
                self._last_state_check = now
                try:
                    is_playing = self._on_player_state_check()
                    if is_playing != self._active:
                        self.set_active(is_playing)
                except Exception as e:
                    if frame % 60 == 0:
                        print(f"[PET] State check error: {e}")

            # Update tkinter dialog if open
            if self._dialog is not None:
                try:
                    self._dialog.update()
                except Exception:
                    pass

            try:
                self._update_animation()
                self._bubble.check_auto_hide()
            except Exception as e:
                print(f"[PET] Animation error: {e}")

            # Adaptive sleep to maintain ~60fps without burning CPU
            elapsed = time.monotonic() - now
            sleep_time = max(0.0, 0.016 - elapsed)
            time.sleep(sleep_time)

        print("[PET] Message loop ended, saving position")
        self._save_position()
        print("[PET] Exiting show()")

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
        try:
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
                    # If bubble is visible, let it handle the click first
                    if self._bubble._visible:
                        if self._bubble.on_click(x, y):
                            return 0
                    zone = self._click_zone.detect(x, y, *self._size)
                    if zone:
                        self._handle_click(zone)
                self._drag_has_moved = False
                return 0

            if msg == win32con.WM_MBUTTONDOWN:
                self._switch_back_to_terminal()
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
        except Exception as e:
            self._log_error(f"WndProc error: {e}")
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
        print(f"[PET] Click zone: {zone}")
        try:
            if zone == "top":
                current = self._get_current_mode()
                target = self._get_next_mode(current)
                if win32gui:
                    rect = win32gui.GetWindowRect(self._hwnd)
                    print(f"[PET] Showing mode bubble: {current} -> {target}")
                    self._bubble.show_mode_bubble(current, target, rect)
            elif zone == "bottom":
                # TEMP: chat input disabled to prevent tkinter crash
                # if win32gui:
                #     rect = win32gui.GetWindowRect(self._hwnd)
                #     self._bubble.show_chat_bubble(rect)
                if self._on_action:
                    self._on_action(zone)
            elif self._on_action:
                print(f"[PET] Calling on_action('{zone}')")
                self._on_action(zone)
                print(f"[PET] on_action('{zone}') done")
        except Exception as e:
            print(f"[PET] Handle click error: {e}")
            self._log_error(f"Handle click error: {e}")

    def _log_error(self, message: str) -> None:
        """Log error to file for debugging."""
        try:
            log_path = Path.home() / ".holle_music" / "pet_errors.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                from datetime import datetime
                f.write(f"[{datetime.now().isoformat()}] {message}\n")
        except Exception:
            pass

    def _get_current_mode(self) -> str:
        # TODO: get current mode from player_proxy
        return "sequential"

    def _get_next_mode(self, current: str) -> str:
        modes = ["sequential", "random", "repeat"]
        idx = modes.index(current) if current in modes else 0
        return modes[(idx + 1) % len(modes)]

    # ── Context menu ──────────────────────────────────────────────────────

    def _show_context_menu(self) -> None:
        print("[PET] Showing context menu")
        try:
            menu = win32gui.CreatePopupMenu()
            win32gui.AppendMenu(menu, win32con.MF_STRING, 1, "Hide")
            win32gui.AppendMenu(menu, win32con.MF_STRING, 2, "Switch to Terminal")
            win32gui.AppendMenu(menu, win32con.MF_STRING, 3, "Quit")

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
            print(f"[PET] Menu command: {cmd}")
            if cmd == 1:
                win32gui.ShowWindow(self._hwnd, win32con.SW_HIDE)
            elif cmd == 2:
                self._switch_back_to_terminal()
            elif cmd == 3:
                self._running = False
                win32gui.DestroyWindow(self._hwnd)
        except Exception as e:
            print(f"[PET] Menu error: {e}")

    def _switch_back_to_terminal(self) -> None:
        """Close pet and launch terminal."""
        print("[PET] Switching back to terminal (middle-click or menu)")
        self._save_position()
        self._launch_terminal()
        self.close()

    def _launch_terminal(self) -> None:
        print(f"[PET] Launching terminal: {sys.executable} -m holle_music")
        subprocess.Popen(
            [sys.executable, "-m", "holle_music"],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

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
