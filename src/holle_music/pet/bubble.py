"""BubbleManager — manages mode-switch and chat bubble windows for the desktop pet."""

from __future__ import annotations

import time
import tkinter as tk
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

from holle_music.pet.bubble_renderer import BubbleRenderer


# ── Win32 constants ───────────────────────────────────────────────────────────
WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000


class BubbleManager:
    """Manage bubble windows: mode-switch confirmation and chat history.

    Uses a single Win32 layered window that is reused between mode and chat
    states.  A tkinter Entry widget is embedded for chat input.
    """

    def __init__(
        self,
        parent_hwnd: int,
        on_action: Callable[[str], None] | None = None,
    ) -> None:
        self._parent_hwnd = parent_hwnd
        self._on_action = on_action
        self._renderer = BubbleRenderer()
        self._hwnd: int = 0
        self._mode: str | None = None  # "mode" or "chat"
        self._messages: list[tuple[str, str]] = []
        self._shown_at: float = 0.0
        self._auto_hide_delay: float = 3.0
        self._hovering: bool = False

        # tkinter input for chat mode
        self._tk_root: tk.Tk | None = None
        self._entry: tk.Entry | None = None
        self._entry_widget: int = 0  # HWND of the Entry widget

        # Button hit boxes for mode bubble (set during show)
        self._confirm_bbox: tuple[int, int, int, int] | None = None
        self._cancel_bbox: tuple[int, int, int, int] | None = None

        self._register_class()

    # ── Public API ────────────────────────────────────────────────────────────

    def show_mode_bubble(
        self,
        current: str,
        target: str,
        pet_rect: tuple[int, int, int, int],
    ) -> None:
        """Show a mode-switch confirmation bubble above the pet."""
        self.hide()
        self._mode = "mode"
        self._shown_at = time.monotonic()

        img = self._renderer.render_mode_bubble(current, target)
        w, h = img.size
        x, y = _calc_position(w, h, pet_rect, above=True)

        # Store button hit boxes (match renderer layout)
        from holle_music.pet.bubble_renderer import PADDING, ARROW_HEIGHT, BUTTON_HEIGHT
        btn_w = (w - PADDING * 3) // 2
        btn_h = BUTTON_HEIGHT
        btn_y = h - ARROW_HEIGHT - btn_h - PADDING // 2
        self._confirm_bbox = (PADDING, btn_y, PADDING + btn_w, btn_y + btn_h)
        self._cancel_bbox = (w - PADDING - btn_w, btn_y, w - PADDING, btn_y + btn_h)

        self._ensure_window(w, h, x, y)
        self._update_layered(img)
        self._show_window()

    def show_chat_bubble(
        self,
        pet_rect: tuple[int, int, int, int],
    ) -> None:
        """Show a chat history bubble above the pet with embedded input."""
        self.hide()
        self._mode = "chat"
        self._shown_at = time.monotonic()

        img = self._renderer.render_chat_bubble(self._messages)
        w, h = img.size
        x, y = _calc_position(w, h, pet_rect, above=True)

        self._ensure_window(w, h, x, y)
        self._update_layered(img)
        self._show_window()
        self._embed_entry(w, h, x, y)

    def hide(self) -> None:
        """Hide the current bubble and clean up tkinter input."""
        if self._hwnd and win32gui is not None:
            win32gui.ShowWindow(self._hwnd, win32con.SW_HIDE)
        self._destroy_entry()
        self._mode = None
        self._confirm_bbox = None
        self._cancel_bbox = None

    def add_message(self, role: str, text: str) -> None:
        """Add a message to chat history."""
        self._messages.append((role, text))
        # Keep last 50 messages
        while len(self._messages) > 50:
            self._messages.pop(0)

    def clear_messages(self) -> None:
        """Clear all chat history."""
        self._messages.clear()

    def check_auto_hide(self) -> None:
        """Hide mode bubble after auto_hide_delay seconds if not hovering."""
        if self._mode != "mode" or self._hovering:
            return
        if time.monotonic() - self._shown_at > self._auto_hide_delay:
            self.hide()

    def on_click(self, x: int, y: int) -> bool:
        """Handle click inside the bubble window.  Return True if handled."""
        if self._mode == "mode":
            return self._on_mode_click(x, y)
        return False

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _register_class(self) -> None:
        if win32gui is None:
            return
        try:
            win32gui.RegisterClass(self._wndclass())
        except Exception:
            pass  # Already registered

    def _wndclass(self) -> object:
        wc = win32gui.WNDCLASS()
        wc.hInstance = win32gui.GetModuleHandle(None)
        wc.lpszClassName = "HolleBubble"
        wc.lpfnWndProc = self._wnd_proc
        return wc

    def _ensure_window(self, w: int, h: int, x: int, y: int) -> None:
        """Create or resize/move the bubble window."""
        if win32gui is None:
            return

        if not self._hwnd:
            ex_style = (
                WS_EX_LAYERED
                | WS_EX_TOOLWINDOW
                | WS_EX_TOPMOST
                | WS_EX_NOACTIVATE
            )
            self._hwnd = win32gui.CreateWindowEx(
                ex_style,
                "HolleBubble",
                "Holle Bubble",
                WS_POPUP,
                x,
                y,
                w,
                h,
                self._parent_hwnd,
                0,
                win32gui.GetModuleHandle(None),
                None,
            )
        else:
            win32gui.SetWindowPos(
                self._hwnd,
                win32con.HWND_TOPMOST,
                x,
                y,
                w,
                h,
                win32con.SWP_SHOWWINDOW,
            )

    def _show_window(self) -> None:
        if self._hwnd and win32gui is not None:
            win32gui.ShowWindow(self._hwnd, win32con.SW_SHOW)
            win32gui.UpdateWindow(self._hwnd)

    def _update_layered(self, img) -> None:
        """Update layered window content from a Pillow RGBA image.

        NOTE: This is a placeholder.  The full DIB-section implementation
        will be shared with PetWindow after the window.py refactor.
        """
        pass  # TODO: implement DIB section rendering (see PetWindow._update_display)

    def _embed_entry(self, w: int, h: int, x: int, y: int) -> None:
        """Embed a tkinter Entry widget at the bottom of the chat bubble."""
        self._destroy_entry()

        self._tk_root = tk.Tk()
        self._tk_root.withdraw()
        self._tk_root.overrideredirect(True)

        entry_h = 26
        entry_y = y + h - entry_h - 8
        self._tk_root.geometry(f"{w - 16}x{entry_h}+{x + 8}+{entry_y}")
        self._tk_root.attributes("-topmost", True)

        self._entry = tk.Entry(
            self._tk_root,
            bg="#2d2d2d",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
            bd=4,
            highlightthickness=0,
            font=("Segoe UI", 10),
        )
        self._entry.pack(fill="both", expand=True)
        self._entry.bind("<Return>", lambda _e: self._on_entry_send())
        self._entry.focus_set()

    def _destroy_entry(self) -> None:
        if self._entry is not None:
            try:
                self._entry.destroy()
            except Exception:
                pass
            self._entry = None
        if self._tk_root is not None:
            try:
                self._tk_root.destroy()
            except Exception:
                pass
            self._tk_root = None

    def _on_entry_send(self) -> None:
        if self._entry is None:
            return
        text = self._entry.get().strip()
        if not text:
            return
        self._entry.delete(0, tk.END)
        self.add_message("user", text)
        if self._on_action:
            self._on_action(f"chat:{text}")

    def _on_mode_click(self, x: int, y: int) -> bool:
        if self._confirm_bbox and _point_in_rect(x, y, self._confirm_bbox):
            if self._on_action:
                self._on_action("top")
            self.hide()
            return True
        if self._cancel_bbox and _point_in_rect(x, y, self._cancel_bbox):
            self.hide()
            return True
        return False

    # ── Window procedure ──────────────────────────────────────────────────────

    def _wnd_proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if msg == win32con.WM_MOUSEMOVE:
            self._hovering = True
            return 0
        if msg == win32con.WM_MOUSELEAVE:
            self._hovering = False
            return 0
        if msg == win32con.WM_LBUTTONDOWN:
            x = win32api.LOWORD(lparam)
            y = win32api.HIWORD(lparam)
            if self.on_click(x, y):
                return 0
        if msg == win32con.WM_DESTROY:
            self._hwnd = 0
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


# ── Utility functions ─────────────────────────────────────────────────────────

def _calc_position(
    w: int,
    h: int,
    pet_rect: tuple[int, int, int, int],
    above: bool = True,
) -> tuple[int, int]:
    """Calculate bubble position centered above (or below) the pet."""
    px, py, px2, py2 = pet_rect
    cx = (px + px2) // 2
    x = cx - w // 2
    y = py - h - 5 if above else py2 + 5
    if y < 0:  # Off-screen top, flip to below
        y = py2 + 5
    return x, y


def _point_in_rect(x: int, y: int, rect: tuple[int, int, int, int]) -> bool:
    """Return True if (x, y) is inside rect (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = rect
    return x0 <= x <= x1 and y0 <= y <= y1
