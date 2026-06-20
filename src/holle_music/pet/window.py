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
    import win32clipboard
    import win32con
    import win32gui
    import win32ui
except ImportError:  # pragma: no cover
    win32api = None  # type: ignore[assignment]
    win32clipboard = None  # type: ignore[assignment]
    win32con = None  # type: ignore[assignment]
    win32gui = None  # type: ignore[assignment]
    win32ui = None  # type: ignore[assignment]

from PIL import Image

from holle_music.pet.bubble import BubbleManager
from holle_music.pet.bubble_renderer import BubbleRenderer
from holle_music.pet.click_zone import ClickZone
from holle_music.pet.renderer import MascotRenderer, CELL_W, CELL_H, PADDING
from holle_music.shared import (
    _SHIMMER_INTERVAL,
    _SHIMMER_PALETTES,
    get_shimmer_palette,
    _MASCOT_COLS,
    _MASCOT_ROWS,
)


class PetWindow:
    """Windows desktop pet window using pywin32 with WS_EX_LAYERED transparent background."""

    def __init__(
        self,
        on_action: Callable[[str], None] | None = None,
        on_double_click: Callable[[], None] | None = None,
        dialog: object | None = None,
    ) -> None:
        self._renderer = MascotRenderer()
        self._click_zone = ClickZone()
        self._on_action = on_action
        self._on_double_click = on_double_click
        self._dialog = dialog
        self._hwnd: int = 0
        self._dragging = False
        self._drag_start = (0, 0)
        self._drag_click_pos: tuple[int, int] | None = None
        self._drag_has_moved = False
        self._drag_start_time = 0.0
        self._mascot_pos = self._load_position()
        self._window_pos = self._mascot_pos
        self._bubble_offset: tuple[int, int] = (0, 0)
        self._window_size: tuple[int, int] = self._calc_size()
        self._last_window_size: tuple[int, int] = self._window_size
        self._mode_hit_rects: list[tuple[str, tuple[int, int, int, int]]] = []
        self._last_eye_update = 0.0
        self._direction = "center"
        self._active = False
        self._shimmer_idx = 0
        self._last_shimmer_update = 0.0
        self._last_state_check = 0.0
        self._running = True
        self._size = self._calc_size()
        self._on_player_state_check: Callable[[], bool] | None = None
        self._on_volume_check: Callable[[], float] | None = None
        self._on_song_end_check: Callable[[], None] | None = None
        self._volume: float = 1.0
        self._last_volume_check: float = 0.0
        self._last_song_end_check: float = 0.0
        self._is_terminal_running: Callable[[], bool] | None = None
        self._on_settings_sync: Callable[[], None] | None = None
        self._last_settings_sync: float = 0.0
        self._bubble_renderer = BubbleRenderer()
        self._bubble = BubbleManager(0, on_action=on_action)
        self._pending_click_zone: str | None = None
        self._pending_click_timer: int | None = None
        self._exit_confirm_pending: bool = False
        self._exit_confirm_time: float = 0.0
        self._last_bubble_rect: tuple[int, int, int, int] | None = None
        self._main_color: str = "light"

    # Timeout before an unanswered exit confirmation auto-dismisses (seconds).
    EXIT_CONFIRM_TIMEOUT: float = 3.0

    def set_chat_submit_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for chat message submission."""
        self._bubble._on_chat_submit = callback

    def set_volume(self, volume: float) -> None:
        """Set current volume (0.0-1.0) and redraw if changed."""
        volume = max(0.0, min(1.0, volume))
        if volume != self._volume:
            self._volume = volume
            self._update_display()

    def set_volume_check(self, callback: Callable[[], float]) -> None:
        """Set a callback that returns the current volume for periodic sync."""
        self._on_volume_check = callback

    def set_song_end_check(self, callback: Callable[[], None]) -> None:
        """Set a callback invoked periodically to advance at song end."""
        self._on_song_end_check = callback

    def set_terminal_check(self, callback: Callable[[], bool]) -> None:
        """Set a callback that returns True if the terminal is running."""
        self._is_terminal_running = callback

    def set_settings_sync(self, callback: Callable[[], None]) -> None:
        """Set a callback invoked periodically to sync settings from the main app."""
        self._on_settings_sync = callback

    def set_main_color(self, color: str) -> None:
        """Set main color theme ("light" or "dark") and redraw."""
        if color != self._main_color:
            self._main_color = color
            self._update_display()

    def show_response_bubble(
        self, text: str, cover: Image.Image | None = None, append: bool = False
    ) -> None:
        """Queue an AI response bubble to be shown in main loop."""
        # A new response overrides the middle-click exit confirmation.
        self._exit_confirm_pending = False
        self._bubble.queue_response(text, cover, append=append)

    def show_status_message(self, text: str) -> None:
        """Show a status message without replacing a loading/thinking bubble.

        If the AI is currently thinking, the status is added as an overlay line
        in the loading bubble. Otherwise a normal response bubble is shown.
        """
        if self._bubble.state == "loading":
            self._bubble.set_loading_overlay(text)
            self._update_display()
        else:
            self.show_response_bubble(text)

    def _check_pending_bubbles(self) -> None:
        """Show any queued response bubbles."""
        result = self._bubble.take_pending_response()
        text = result[0] if isinstance(result, tuple) else result
        cover = result[1] if isinstance(result, tuple) else None
        append = result[2] if isinstance(result, tuple) and len(result) > 2 else False
        if text:
            self._log_error(f"[bubble] pending response received, len={len(text)}")
            if win32gui:
                self._bubble.show_response(text, cover, append=append)
                self._log_error("[bubble] show_response called")
                # Force a redraw so the response appears immediately.
                self._update_display()

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

        self._bubble._parent_hwnd = self._hwnd
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

            # Sync playing state for shimmer (throttle to 0.5s)
            now = time.monotonic()
            if self._on_player_state_check is not None and now - self._last_state_check >= 0.5:
                self._last_state_check = now
                is_playing = self._on_player_state_check()
                if is_playing != self._active:
                    self.set_active(is_playing)

            # Sync volume for shimmer height (throttle to 0.5s)
            if self._on_volume_check is not None and now - self._last_volume_check >= 0.5:
                self._last_volume_check = now
                try:
                    new_volume = self._on_volume_check()
                    self.set_volume(new_volume)
                except Exception:
                    pass

            # Auto-advance to next song when standalone playback ends.
            if self._on_song_end_check is not None and now - self._last_song_end_check >= 0.5:
                self._last_song_end_check = now
                try:
                    self._on_song_end_check()
                except Exception:
                    pass

            # Sync settings (color / main_color) from the main app.
            if self._on_settings_sync is not None and now - self._last_settings_sync >= 1.0:
                self._last_settings_sync = now
                try:
                    self._on_settings_sync()
                except Exception:
                    pass

            # Update tkinter dialog if open
            if self._dialog is not None:
                try:
                    self._dialog.update()
                except Exception:
                    pass

            # Process bubble state timers and pending responses
            try:
                if self._bubble.update():
                    self._update_display()
                self._check_pending_bubbles()
            except Exception:
                pass

            # Auto-dismiss exit confirmation after timeout.
            if self._exit_confirm_pending:
                if (
                    self._bubble.state != "response"
                    or time.monotonic() - self._exit_confirm_time >= self.EXIT_CONFIRM_TIMEOUT
                ):
                    self._exit_confirm_pending = False
                    if self._bubble.state == "response":
                        self._bubble.hide_response()
                        self._update_display()

            try:
                self._update_animation()
            except Exception as e:
                print(f"[PET] Animation error: {e}")

            # Adaptive sleep to maintain ~60fps without burning CPU
            elapsed = time.monotonic() - now
            sleep_time = max(0.0, 0.016 - elapsed)
            time.sleep(sleep_time)

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
        width = _MASCOT_COLS * CELL_W + PADDING * 2
        height = _MASCOT_ROWS * CELL_H + PADDING * 2
        return width, height

    def _create_window(self) -> int:
        wndclass = win32gui.WNDCLASS()
        wndclass.hInstance = win32gui.GetModuleHandle(None)
        wndclass.lpszClassName = "HollePetWindow"
        wndclass.lpfnWndProc = self._wnd_proc
        wndclass.style = win32con.CS_DBLCLKS
        win32gui.RegisterClass(wndclass)

        w, h = self._window_size

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
                self._mascot_pos = (
                    self._mascot_pos[0] + dx,
                    self._mascot_pos[1] + dy,
                )
                self._drag_start = (cx, cy)
                self._window_pos = (
                    self._mascot_pos[0] - self._bubble_offset[0],
                    self._mascot_pos[1] - self._bubble_offset[1],
                )
                win32gui.SetWindowPos(
                    hwnd, 0,
                    self._window_pos[0], self._window_pos[1],
                    0, 0,
                    win32con.SWP_NOSIZE | win32con.SWP_NOZORDER,
                )
            else:
                # Eye tracking uses pet-relative coordinates.
                self._update_eye_direction(x - self._bubble_offset[0], y - self._bubble_offset[1])
            return 0

        if msg == win32con.WM_CHAR:
            # Append printable characters to the input bubble.
            if self._bubble.state == "input":
                try:
                    char = chr(wparam)
                    self._bubble.input_append(char)
                    self._update_display()
                except Exception:
                    pass
            return 0

        if msg == win32con.WM_KEYDOWN:
            if self._bubble.state == "input":
                ctrl = bool(win32api.GetAsyncKeyState(win32con.VK_CONTROL) & 0x8000)
                if ctrl and wparam == ord("V"):
                    if win32clipboard is not None:
                        try:
                            win32clipboard.OpenClipboard()
                            data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                            win32clipboard.CloseClipboard()
                            if data:
                                self._bubble.input_paste(str(data))
                                self._update_display()
                        except Exception:
                            pass
                    return 0
                if ctrl and wparam == ord("C"):
                    if win32clipboard is not None:
                        try:
                            text = self._bubble.input_copy()
                            win32clipboard.OpenClipboard()
                            win32clipboard.EmptyClipboard()
                            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                            win32clipboard.CloseClipboard()
                        except Exception:
                            pass
                    return 0
                if ctrl and wparam == ord("A"):
                    self._bubble.input_select_all()
                    self._update_display()
                    return 0
                if wparam == win32con.VK_BACK:
                    self._bubble.input_backspace()
                    self._update_display()
                    return 0
                if wparam == win32con.VK_RETURN:
                    self._log_error(f"[window] VK_RETURN, text len={len(self._bubble.input_text)}")
                    self._bubble.submit_input()
                    self._update_display()
                    return 0
                if wparam == win32con.VK_UP:
                    if self._bubble.input_history_up():
                        self._update_display()
                    return 0
                if wparam == win32con.VK_DOWN:
                    if self._bubble.input_history_down():
                        self._update_display()
                    return 0
            return 0

        if msg == win32con.WM_LBUTTONDOWN:
            x = win32api.LOWORD(lparam)
            y = win32api.HIWORD(lparam)
            pet_x = x - self._bubble_offset[0]
            pet_y = y - self._bubble_offset[1]
            pet_w, pet_h = self._size
            in_pet = 0 <= pet_x < pet_w and 0 <= pet_y < pet_h

            # If the mode picker is open, check its squares first.
            if self._bubble.mode_active:
                mode = self._hit_test_mode(pet_x, pet_y)
                if mode:
                    self._bubble.select_mode(mode)
                    self._update_display()
                    return 0
                # Click outside the squares dismisses the mode picker.
                self._bubble.hide_mode_picker()
                self._update_display()
                return 0

            # Only start dragging when the user presses on the mascot body.
            # Bubbles (input/response/loading) are no longer dismissed by left
            # click; middle click is used for that instead.
            if not in_pet:
                return 0

            self._dragging = True
            self._drag_has_moved = False
            self._drag_start = win32api.GetCursorPos()
            self._drag_click_pos = (pet_x, pet_y)
            self._drag_start_time = time.monotonic()
            return 0

        if msg == win32con.WM_LBUTTONUP:
            x = win32api.LOWORD(lparam)
            y = win32api.HIWORD(lparam)
            pet_x = x - self._bubble_offset[0]
            pet_y = y - self._bubble_offset[1]
            self._dragging = False
            press_duration = time.monotonic() - self._drag_start_time
            is_click = (not self._drag_has_moved) and (press_duration < 0.2)
            if is_click and self._drag_click_pos and self._bubble.state != "input":
                zone = self._click_zone.detect(pet_x, pet_y, *self._size)
                if zone:
                    # Defer single-click execution briefly so a double-click can
                    # cancel it; this prevents play/pause from firing on dblclk.
                    self._pending_click_zone = zone
                    self._pending_click_timer = 2
                    import ctypes
                    ctypes.windll.user32.SetTimer(hwnd, 2, 200, None)
            self._drag_has_moved = False
            return 0

        if msg == win32con.WM_LBUTTONDBLCLK:
            x = win32api.LOWORD(lparam)
            y = win32api.HIWORD(lparam)
            pet_x = x - self._bubble_offset[0]
            pet_y = y - self._bubble_offset[1]
            pet_w, pet_h = self._size
            in_pet = 0 <= pet_x < pet_w and 0 <= pet_y < pet_h
            # Cancel any pending single click.
            if self._pending_click_timer is not None:
                import ctypes
                ctypes.windll.user32.KillTimer(hwnd, self._pending_click_timer)
                self._pending_click_timer = None
            self._pending_click_zone = None
            self._dragging = False
            self._drag_has_moved = False
            if in_pet and self._on_double_click:
                try:
                    self._on_double_click()
                except Exception as e:
                    print(f"[PET] Double-click error: {e}")
            return 0

        if msg == win32con.WM_MBUTTONDOWN:
            # Exit confirmation:
            # - First middle-click with no bubble -> ask for confirmation.
            # - Confirmation showing:
            #     * middle-click on the bubble -> cancel
            #     * middle-click outside the bubble -> confirm (switch/close)
            # - Any other active bubble is dismissed normally.
            x = win32api.LOWORD(lparam)
            y = win32api.HIWORD(lparam)
            rect = self._last_bubble_rect
            on_bubble = (
                rect is not None
                and rect[0] <= x <= rect[2]
                and rect[1] <= y <= rect[3]
            )

            if self._exit_confirm_pending and self._bubble.state == "response":
                if on_bubble:
                    # Cancel: dismiss the confirmation bubble.
                    self._bubble.hide_response()
                    self._exit_confirm_pending = False
                    self._update_display()
                else:
                    # Confirm: switch back to terminal / close pet.
                    self._switch_back_to_terminal()
            elif self._bubble.has_active_bubble:
                if self._bubble.state == "input":
                    self._bubble.hide_input()
                elif self._bubble.state == "response":
                    self._bubble.hide_response()
                elif self._bubble.state == "loading":
                    self._bubble.hide_loading()
                elif self._bubble.state == "mode":
                    self._bubble.hide_mode_picker()
                # Reset any leftover drag/click state so the next left click is
                # processed as a fresh click instead of being ignored.
                self._dragging = False
                self._drag_has_moved = False
                self._drag_click_pos = None
                self._ignore_next_click = False
                self._exit_confirm_pending = False
                self._update_display()
            elif not self._exit_confirm_pending:
                self.show_response_bubble("确定要退出吗？再点击一次即可")
                self._exit_confirm_pending = True
                self._exit_confirm_time = time.monotonic()
            else:
                self._switch_back_to_terminal()
            return 0

        if msg == win32con.WM_MOUSEWHEEL:
            import ctypes
            delta = ctypes.c_short(wparam >> 16).value
            if delta > 0:
                self._on_action("volume_up") if self._on_action else None
            else:
                self._on_action("volume_down") if self._on_action else None
            return 0

        if msg == win32con.WM_RBUTTONUP:
            if self._bubble.state == "input":
                if win32clipboard is not None:
                    try:
                        win32clipboard.OpenClipboard()
                        data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                        win32clipboard.CloseClipboard()
                        if data:
                            self._bubble.input_paste(str(data))
                            self._update_display()
                    except Exception:
                        pass
            else:
                self._show_context_menu()
            return 0

        if msg == win32con.WM_TIMER:
            if wparam == 2:
                # Pending single-click timer fired: execute the click.
                zone = self._pending_click_zone
                self._pending_click_zone = None
                self._pending_click_timer = None
                if zone:
                    try:
                        self._handle_click(zone)
                    except Exception as e:
                        print(f"[PET] Click error: {e}")
                return 0
            self._update_animation()
            return 0

        if msg == win32con.WM_DESTROY:
            self._running = False
            import ctypes
            try:
                ctypes.windll.user32.KillTimer(hwnd, 1)
            except Exception:
                pass
            try:
                ctypes.windll.user32.KillTimer(hwnd, 2)
            except Exception:
                pass
            win32gui.PostQuitMessage(0)
            return 0

        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _track_mouse_global(self) -> None:
        """Update eye direction based on global mouse position."""
        try:
            mx, my = win32api.GetCursorPos()
            rect = win32gui.GetWindowRect(self._hwnd)
            rel_x = mx - rect[0] - self._bubble_offset[0]
            rel_y = my - rect[1] - self._bubble_offset[1]
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
        palette = _SHIMMER_PALETTES[get_shimmer_palette()]
        self._shimmer_idx = (self._shimmer_idx + 1) % len(palette)
        self._update_display()

    def _update_display(self) -> None:
        if not self._hwnd or win32gui is None:
            return

        try:
            self._do_update_display()
        except Exception as e:
            self._log_error(f"_update_display error: {e}")

    def _do_update_display(self) -> None:
        """Actual display update; exceptions are caught by _update_display."""
        import ctypes
        from ctypes import wintypes

        pet_img = self._renderer.render(
            self._direction,
            self._active,
            palette_name=get_shimmer_palette(),
            shimmer_idx=self._shimmer_idx,
            volume=self._volume,
            main_color=self._main_color,
        )

        layout = self._compute_layout(pet_img.size)
        self._window_size = layout["window_size"]
        self._bubble_offset = layout["bubble_offset"]
        self._mode_hit_rects = layout["mode_hit_rects"]

        # Keep the mascot at the same screen position when the bubble changes.
        new_window_pos = (
            self._mascot_pos[0] - self._bubble_offset[0],
            self._mascot_pos[1] - self._bubble_offset[1],
        )
        if (
            new_window_pos != self._window_pos
            or self._window_size != self._last_window_size
        ):
            win32gui.SetWindowPos(
                self._hwnd,
                0,
                new_window_pos[0],
                new_window_pos[1],
                self._window_size[0],
                self._window_size[1],
                win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE,
            )
            self._window_pos = new_window_pos
            self._last_window_size = self._window_size

        # Composite mascot and bubble onto a single canvas.
        canvas = Image.new("RGBA", self._window_size, (0, 0, 0, 0))
        canvas.paste(pet_img, self._bubble_offset, pet_img)
        if layout["bubble_image"] is not None and layout["bubble_pos"] is not None:
            bubble_img = layout["bubble_image"]
            bx = self._bubble_offset[0] + layout["bubble_pos"][0]
            by = self._bubble_offset[1] + layout["bubble_pos"][1]
            canvas.paste(bubble_img, (bx, by), bubble_img)
            self._last_bubble_rect = (bx, by, bx + bubble_img.width, by + bubble_img.height)
        else:
            self._last_bubble_rect = None

        w, h = canvas.size
        img_bytes = canvas.tobytes("raw", "BGRA")

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

    def _diagonal_bubble_position(
        self,
        pet_w: int,
        pet_h: int,
        bubble_w: int,
        bubble_h: int,
        force_h: str | None = None,
        force_v: str | None = None,
    ) -> tuple[int, int]:
        """Place a bubble diagonally, leaving a gap of two body cells.

        Pet in the upper-right  -> bubble goes to lower-left.
        Pet in the lower-left  -> bubble goes to upper-right.
        The gap between the mascot content edges and the bubble is kept at
        two body rectangles (2 * CELL_H) so the bubble never sits flush.
        """
        # The bubble slightly overlaps the mascot content by 10px.
        gap = -19.5

        mx, my = self._mascot_pos
        mid_x, mid_y = self._screen_center()
        content_left, content_top, content_right, content_bottom = self._renderer.content_rect()

        # Pick the side with more screen space, or use forced side.
        if force_h == "left":
            x = content_left - bubble_w - gap
        elif force_h == "right":
            x = content_right + gap
        elif mx + pet_w // 2 > mid_x:
            x = content_left - bubble_w - gap
        else:
            x = content_right + gap

        if force_v == "top":
            y = content_top - bubble_h - gap
        elif force_v == "bottom":
            y = content_bottom + gap
        elif my + pet_h // 2 > mid_y:
            y = content_top - bubble_h - gap
        else:
            y = content_bottom + gap

        return int(round(x)), int(round(y))

    def _screen_center(self) -> tuple[int, int]:
        """Return the screen center point."""
        try:
            sw = win32api.GetSystemMetrics(0)
            sh = win32api.GetSystemMetrics(1)
        except Exception:
            sw, sh = 1920, 1080
        return sw // 2, sh // 2

    def _compute_layout(
        self, pet_size: tuple[int, int]
    ) -> dict:
        """Compute window layout for the current bubble state.

        Returns a dict with:
        - window_size: (width, height) of the layered window
        - bubble_offset: (x, y) where the pet is placed inside the window
        - bubble_pos: (x, y) where the bubble is placed relative to the pet
        - bubble_image: rendered bubble PIL Image or None
        - mode_hit_rects: list of (mode, rect) for click testing
        """
        pet_w, pet_h = pet_size
        bubble_image: Image.Image | None = None
        bubble_pos: tuple[int, int] | None = None
        mode_hit_rects: list[tuple[str, tuple[int, int, int, int]]] = []

        if self._bubble.state == "input":
            bubble_image = self._bubble_renderer.render_input_bubble(
                self._bubble.input_text,
                self._bubble.cursor_visible,
                self._bubble.input_selection,
            )
            # Center horizontally over the mascot content; place above/below
            # based on vertical screen position, with a small gap from the pet.
            content_left, content_top, content_right, content_bottom = self._renderer.content_rect()
            x = (content_left + content_right - bubble_image.width) // 2
            try:
                sh = win32api.GetSystemMetrics(1)
            except Exception:
                sh = 1080
            my = self._mascot_pos[1]
            if my + pet_h // 2 > sh // 2:
                y = content_top - bubble_image.height - 20
            else:
                y = content_bottom + 20
            bubble_pos = (x, y)

        elif self._bubble.state == "response":
            bubble_image = self._bubble_renderer.render_response_bubble(
                self._bubble.response_text,
                cover_image=self._bubble.response_cover,
            )
            bubble_pos = self._diagonal_bubble_position(
                pet_w, pet_h, bubble_image.width, bubble_image.height
            )

        elif self._bubble.state == "loading":
            bubble_image = self._bubble_renderer.render_loading_bubble(
                self._bubble.loading_frame,
                self._bubble.loading_overlay,
            )
            bubble_pos = self._diagonal_bubble_position(
                pet_w, pet_h, bubble_image.width, bubble_image.height
            )

        elif self._bubble.state == "mode":
            current_mode = self._get_current_mode()
            bubble_image = self._bubble_renderer.render_mode_picker(current_mode)
            content_left, content_top, content_right, content_bottom = self._renderer.content_rect()
            x = (content_left + content_right - bubble_image.width) // 2
            y = content_top - bubble_image.height
            bubble_pos = (x, y)
            # Build hit rectangles for the three mode squares.
            sq = 40
            pad = 14
            total_content = sq * 3
            remaining = bubble_image.width - total_content - pad * 2
            gap = remaining // 2
            sq_y = (bubble_image.height - sq) // 2
            modes = ["sequential", "random", "repeat"]
            for i, mode in enumerate(modes):
                sq_x = pad + i * (sq + gap)
                rect = (
                    x + sq_x,
                    y + sq_y,
                    x + sq_x + sq,
                    y + sq_y + sq,
                )
                mode_hit_rects.append((mode, rect))

        if bubble_pos is None or bubble_image is None:
            return {
                "window_size": pet_size,
                "bubble_offset": (0, 0),
                "bubble_pos": None,
                "bubble_image": None,
                "mode_hit_rects": [],
            }

        bx, by = bubble_pos
        bx2 = bx + bubble_image.width
        by2 = by + bubble_image.height

        # Avoid extending past screen edges.
        try:
            sw = win32api.GetSystemMetrics(0)
            sh = win32api.GetSystemMetrics(1)
        except Exception:
            sw, sh = 1920, 1080

        mx, my = self._mascot_pos

        # If the input bubble would extend past the top or bottom screen edge,
        # flip it to the opposite vertical side of the pet.
        if self._bubble.state == "input":
            content_left, content_top, content_right, content_bottom = self._renderer.content_rect()
            if my + by2 > sh - 20:
                by = content_top - bubble_image.height - 20
                by2 = by + bubble_image.height
                bubble_pos = (bx, by)
            elif my + by < 20:
                by = content_bottom + 20
                by2 = by + bubble_image.height
                bubble_pos = (bx, by)

        # Diagonal response/loading bubbles: flip horizontally if they would
        # extend past the left or right screen edge.
        if self._bubble.state in ("response", "loading"):
            if mx + bx < 4:
                bx, by = self._diagonal_bubble_position(
                    pet_w, pet_h, bubble_image.width, bubble_image.height, force_h="right"
                )
                bx2 = bx + bubble_image.width
                by2 = by + bubble_image.height
                bubble_pos = (bx, by)
            elif mx + bx2 > sw - 4:
                bx, by = self._diagonal_bubble_position(
                    pet_w, pet_h, bubble_image.width, bubble_image.height, force_h="left"
                )
                bx2 = bx + bubble_image.width
                by2 = by + bubble_image.height
                bubble_pos = (bx, by)

        # If a bubble placed above the pet (response/loading/mode)
        # would go above the visible screen, move it below the pet instead.
        if self._bubble.state == "mode" and my + by < 4:
            content_left, content_top, content_right, content_bottom = self._renderer.content_rect()
            by = content_bottom
            by2 = by + bubble_image.height
            bubble_pos = (bx, by)
            # Rebuild mode hit rectangles after moving below the pet.
            mode_hit_rects = []
            sq = 40
            pad = 14
            total_content = sq * 3
            remaining = bubble_image.width - total_content - pad * 2
            gap = remaining // 2
            sq_y = (bubble_image.height - sq) // 2
            modes = ["sequential", "random", "repeat"]
            for i, mode in enumerate(modes):
                sq_x = pad + i * (sq + gap)
                rect = (bx + sq_x, by + sq_y, bx + sq_x + sq, by + sq_y + sq)
                mode_hit_rects.append((mode, rect))
        elif self._bubble.state in ("response", "loading") and my + by < 4:
            bx, by = self._diagonal_bubble_position(
                pet_w, pet_h, bubble_image.width, bubble_image.height, force_v="bottom"
            )
            bx2 = bx + bubble_image.width
            by2 = by + bubble_image.height
            bubble_pos = (bx, by)

        # Final safety clamp: keep the entire bubble on screen.  This catches
        # long input bubbles near the left/right edges and diagonal response
        # bubbles that still overflow after flipping.
        try:
            sw = win32api.GetSystemMetrics(0)
            sh = win32api.GetSystemMetrics(1)
        except Exception:
            sw, sh = 1920, 1080

        mx, my = self._mascot_pos
        bubble_w = bubble_image.width
        bubble_h = bubble_image.height
        bx, by = bubble_pos

        if mx + bx < 4:
            bx = 4 - mx
        elif mx + bx + bubble_w > sw - 4:
            bx = sw - 4 - bubble_w - mx

        if my + by < 4:
            by = 4 - my
        elif my + by + bubble_h > sh - 4:
            by = sh - 4 - bubble_h - my

        bubble_pos = (bx, by)
        bx2 = bx + bubble_w
        by2 = by + bubble_h

        # If the mode picker moved, rebuild its hit rectangles at the final position.
        if self._bubble.state == "mode":
            mode_hit_rects = []
            sq = 40
            pad = 14
            total_content = sq * 3
            remaining = bubble_image.width - total_content - pad * 2
            gap = remaining // 2
            sq_y = (bubble_image.height - sq) // 2
            modes = ["sequential", "random", "repeat"]
            for i, mode in enumerate(modes):
                sq_x = pad + i * (sq + gap)
                rect = (bx + sq_x, by + sq_y, bx + sq_x + sq, by + sq_y + sq)
                mode_hit_rects.append((mode, rect))

        min_x = min(0, bx)
        min_y = min(0, by)
        max_x = max(pet_w, bx2)
        max_y = max(pet_h, by2)

        window_size = (max_x - min_x, max_y - min_y)
        bubble_offset = (-min_x, -min_y)

        return {
            "window_size": window_size,
            "bubble_offset": bubble_offset,
            "bubble_pos": bubble_pos,
            "bubble_image": bubble_image,
            "mode_hit_rects": mode_hit_rects,
        }

    def _hit_test_mode(self, pet_x: int, pet_y: int) -> str:
        """Return the mode under the given pet-relative coordinate, or empty string."""
        for mode, rect in self._mode_hit_rects:
            x1, y1, x2, y2 = rect
            if x1 <= pet_x < x2 and y1 <= pet_y < y2:
                return mode
        return ""

    # ── Click handling ────────────────────────────────────────────────────

    def _handle_click(self, zone: str) -> None:
        if zone == "top":
            # One click on the top zone cycles to the next play mode; the
            # callback shows a reply bubble with the new mode label.
            if self._on_action:
                self._on_action("top")
        elif zone == "bottom":
            self._bubble.toggle_input()
            if self._bubble.state == "input":
                try:
                    win32gui.SetForegroundWindow(self._hwnd)
                    win32gui.SetActiveWindow(self._hwnd)
                    win32gui.SetFocus(self._hwnd)
                except Exception:
                    pass
            self._update_display()
        elif self._on_action:
            self._on_action(zone)

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
        """Read current play mode from the shared state file."""
        try:
            state_path = Path.home() / ".holle_music" / "pet_state.json"
            if state_path.exists():
                data = json.loads(state_path.read_text(encoding="utf-8"))
                mode = data.get("mode", "sequential")
                if mode in ("sequential", "random", "repeat"):
                    return mode
        except Exception:
            pass
        return "sequential"

    def _get_next_mode(self, current: str) -> str:
        modes = ["sequential", "random", "repeat"]
        idx = modes.index(current) if current in modes else 0
        return modes[(idx + 1) % len(modes)]

    # ── Context menu ──────────────────────────────────────────────────────

    def _show_context_menu(self) -> None:
        try:
            menu = win32gui.CreatePopupMenu()
            if self._bubble.state == "response" and self._bubble.response_text:
                win32gui.AppendMenu(menu, win32con.MF_STRING, 4, "Copy reply")
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
            if cmd == 1:
                win32gui.ShowWindow(self._hwnd, win32con.SW_HIDE)
            elif cmd == 2:
                self._switch_back_to_terminal()
            elif cmd == 3:
                self._running = False
                win32gui.DestroyWindow(self._hwnd)
            elif cmd == 4:
                self._copy_to_clipboard(self._bubble.response_text)
        except Exception as e:
            print(f"[PET] Menu error: {e}")

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to the Windows clipboard."""
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
        except Exception as e:
            self._log_error(f"Clipboard error: {e}")

    def _switch_back_to_terminal(self) -> None:
        """Close pet and return focus to the terminal if it is running."""
        self._save_position()
        if self._is_terminal_running is not None and self._is_terminal_running():
            self._bring_terminal_to_front()
        self.close()

    def _bring_terminal_to_front(self) -> None:
        """Find the terminal window and bring it to the foreground."""
        try:
            handles: list[int] = []

            def _enum(hwnd: int, _: object) -> bool:
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title and "Holle Music" in title:
                        handles.append(hwnd)
                return True

            win32gui.EnumWindows(_enum, None)
            if handles:
                hwnd = handles[0]
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
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
                json.dumps({"x": self._mascot_pos[0], "y": self._mascot_pos[1]}),
                encoding="utf-8",
            )
        except Exception:
            pass
