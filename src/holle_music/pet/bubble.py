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
        on_chat_submit: Callable[[str], None] | None = None,
    ) -> None:
        self._parent_hwnd = parent_hwnd
        self._on_action = on_action
        self._on_chat_submit = on_chat_submit
        self._renderer = BubbleRenderer()
        self._hwnd: int = 0
        self._mode: str | None = None  # "mode" or "chat"
        self._messages: list[tuple[str, str]] = []
        self._shown_at: float = 0.0
        self._auto_hide_delay: float = 3.0
        self._hovering: bool = False
        self._visible: bool = False

        # tkinter chat window
        self._tk_root: tk.Tk | None = None
        self._chat_window: tk.Toplevel | None = None
        self._chat_text: tk.Text | None = None
        self._chat_entry: tk.Entry | None = None

        self._ensure_tk_root()

        # Button hit boxes for mode bubble (set during show)
        self._confirm_bbox: tuple[int, int, int, int] | None = None
        self._cancel_bbox: tuple[int, int, int, int] | None = None

        self._register_class()

    def _ensure_tk_root(self) -> None:
        """Pre-create hidden tkinter root window."""
        if self._tk_root is not None:
            return
        try:
            self._tk_root = tk.Tk()
            self._tk_root.withdraw()
            self._tk_root.overrideredirect(True)
        except Exception as e:
            self._log_error(f"Failed to create tkinter root: {e}")
            self._tk_root = None

    # ── Public API ────────────────────────────────────────────────────────────

    def show_mode_bubble(
        self,
        current: str,
        target: str,
        pet_rect: tuple[int, int, int, int],
    ) -> None:
        """Show a mode-switch confirmation bubble above the pet."""
        try:
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
            self._visible = True
        except Exception as e:
            self._log_error(f"show_mode_bubble error: {e}")

    def show_chat_bubble(
        self,
        pet_rect: tuple[int, int, int, int],
    ) -> None:
        """Show a tkinter chat window near the pet."""
        try:
            self.hide()
            self._mode = "chat"
            self._shown_at = time.monotonic()

            # Use pure tkinter window for chat (better input handling)
            self._ensure_tk_root()
            if self._tk_root is None:
                return

            self._build_chat_window(pet_rect)
            self._visible = True
        except Exception as e:
            self._log_error(f"show_chat_bubble error: {e}")

    def hide(self) -> None:
        """Hide the current bubble and clean up tkinter chat window."""
        if self._hwnd and win32gui is not None:
            try:
                win32gui.ShowWindow(self._hwnd, win32con.SW_HIDE)
            except Exception:
                pass
        if self._chat_window is not None:
            try:
                self._chat_window.destroy()
            except Exception:
                pass
            self._chat_window = None
        self._mode = None
        self._visible = False
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
        """Update layered window content from a Pillow RGBA image."""
        if not self._hwnd or win32gui is None:
            return

        import ctypes
        from ctypes import wintypes

        w, h = img.size
        img_bytes = img.tobytes("raw", "BGRA")
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
        bmi.bmiHeader.biHeight = -h
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0

        hdc_screen = win32gui.GetDC(0)
        hdc_mem = win32gui.CreateCompatibleDC(hdc_screen)

        ppvBits = ctypes.c_void_p()
        hbmp = gdi32.CreateDIBSection(
            hdc_screen,
            ctypes.byref(bmi),
            0,
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

        rect = win32gui.GetWindowRect(self._hwnd)
        pt_src = _POINT(0, 0)
        sz = _SIZE(w, h)
        pt_dst = _POINT(rect[0], rect[1])
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

    def _on_entry_send(self) -> None:
        if self._chat_entry is None:
            return
        text = self._chat_entry.get().strip()
        if not text:
            return
        self._chat_entry.delete(0, tk.END)
        self.add_message("user", text)
        self._refresh_chat_text()
        if self._on_chat_submit:
            self._on_chat_submit(text)
        elif self._on_action:
            self._on_action(f"chat:{text}")

    def _build_chat_window(self, pet_rect: tuple[int, int, int, int]) -> None:
        """Build a pure tkinter chat window positioned near the pet."""
        if self._tk_root is None:
            return

        # Destroy existing chat window if any
        if self._chat_window is not None:
            try:
                self._chat_window.destroy()
            except Exception:
                pass

        width = 320
        height = 260
        x, y = _calc_position(width, height, pet_rect, above=True)

        self._chat_window = tk.Toplevel(self._tk_root)
        self._chat_window.overrideredirect(True)
        self._chat_window.attributes("-topmost", True)
        self._chat_window.geometry(f"{width}x{height}+{x}+{y}")
        self._chat_window.configure(bg="#252525")

        # Close on Escape
        self._chat_window.bind("<Escape>", lambda _e: self.hide())

        # Title bar
        title_frame = tk.Frame(self._chat_window, bg="#1e1e1e", height=28)
        title_frame.pack(fill="x")
        title_frame.pack_propagate(False)

        tk.Label(
            title_frame,
            text="Holle Chat",
            fg="white",
            bg="#1e1e1e",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=8, pady=2)

        close_btn = tk.Label(
            title_frame,
            text="✕",
            fg="#ff4444",
            bg="#1e1e1e",
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        )
        close_btn.pack(side="right", padx=8, pady=2)
        close_btn.bind("<Button-1>", lambda _e: self.hide())

        # Chat history
        self._chat_text = tk.Text(
            self._chat_window,
            bg="#252525",
            fg="white",
            font=("Segoe UI", 10),
            wrap="word",
            state="disabled",
            relief="flat",
            padx=8,
            pady=8,
            highlightthickness=0,
            bd=0,
        )
        self._chat_text.pack(fill="both", expand=True)

        # Input area
        input_frame = tk.Frame(self._chat_window, bg="#252525")
        input_frame.pack(fill="x", padx=8, pady=8)

        self._chat_entry = tk.Entry(
            input_frame,
            bg="#333333",
            fg="white",
            insertbackground="white",
            relief="flat",
            bd=6,
            highlightthickness=0,
            font=("Segoe UI", 10),
        )
        self._chat_entry.pack(side="left", fill="x", expand=True)
        self._chat_entry.bind("<Return>", lambda _e: self._on_entry_send())
        self._chat_entry.focus_force()

        send_btn = tk.Label(
            input_frame,
            text="➤",
            fg="#ff69b4",
            bg="#252525",
            font=("Segoe UI", 12),
            cursor="hand2",
        )
        send_btn.pack(side="right", padx=(8, 0))
        send_btn.bind("<Button-1>", lambda _e: self._on_entry_send())

        self._refresh_chat_text()

        # Make window draggable by title bar
        self._drag_start_x = 0
        self._drag_start_y = 0

        def start_drag(event):
            self._drag_start_x = event.x_root - x
            self._drag_start_y = event.y_root - y

        def do_drag(event):
            new_x = event.x_root - self._drag_start_x
            new_y = event.y_root - self._drag_start_y
            self._chat_window.geometry(f"+{new_x}+{new_y}")

        title_frame.bind("<Button-1>", start_drag)
        title_frame.bind("<B1-Motion>", do_drag)

    def _refresh_chat_text(self) -> None:
        """Refresh chat history display."""
        if self._chat_text is None:
            return
        self._chat_text.config(state="normal")
        self._chat_text.delete("1.0", tk.END)
        for role, text in self._messages:
            if role == "user":
                self._chat_text.insert(tk.END, "你: ", "user")
                self._chat_text.insert(tk.END, f"{text}\n", "user_text")
            elif role == "ai":
                self._chat_text.insert(tk.END, "AI: ", "ai")
                self._chat_text.insert(tk.END, f"{text}\n\n", "ai_text")
        self._chat_text.tag_config("user", foreground="#ff69b4", font=("Segoe UI", 9, "bold"))
        self._chat_text.tag_config("ai", foreground="#aaaaaa", font=("Segoe UI", 9, "bold"))
        self._chat_text.tag_config("user_text", foreground="white")
        self._chat_text.tag_config("ai_text", foreground="white")
        self._chat_text.config(state="disabled")
        self._chat_text.see(tk.END)

    def refresh_chat(self) -> None:
        """Public method to refresh chat display after new messages."""
        self._refresh_chat_text()

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

    def _log_error(self, message: str) -> None:
        """Log error to file for debugging."""
        try:
            from pathlib import Path
            from datetime import datetime
            log_path = Path.home() / ".holle_music" / "pet_errors.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().isoformat()}] {message}\n")
        except Exception:
            pass


# ── Utility functions ─────────────────────────────────────────────────────────

def _calc_position(
    w: int,
    h: int,
    pet_rect: tuple[int, int, int, int],
    above: bool = True,
) -> tuple[int, int]:
    """Calculate bubble position above/below pet, keeping inside screen bounds."""
    px, py, px2, py2 = pet_rect
    cx = (px + px2) // 2

    # Get screen dimensions
    try:
        screen_w = win32api.GetSystemMetrics(0)
        screen_h = win32api.GetSystemMetrics(1)
    except Exception:
        screen_w, screen_h = 1920, 1080

    # Default: centered above pet
    x = cx - w // 2
    y = py - h - 5 if above else py2 + 5

    # If going above puts it off-screen top, flip below
    if y < 0:
        y = py2 + 5

    # Keep horizontal inside screen bounds
    if x < 5:
        x = 5
    elif x + w > screen_w - 5:
        x = screen_w - w - 5

    # If pet is near left edge, prefer bubble to the right of pet
    if px < w + 20:
        x = px2 + 10
        # But keep inside right edge
        if x + w > screen_w - 5:
            x = screen_w - w - 5
    # If pet is near right edge, prefer bubble to the left of pet
    elif px2 > screen_w - w - 20:
        x = px - w - 10
        if x < 5:
            x = 5

    return x, y


def _point_in_rect(x: int, y: int, rect: tuple[int, int, int, int]) -> bool:
    """Return True if (x, y) is inside rect (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = rect
    return x0 <= x <= x1 and y0 <= y <= y1
