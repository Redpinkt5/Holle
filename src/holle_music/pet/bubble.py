"""Bubble system — floating UI for input, responses, and mode switching."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

BG = "#151515"
ACCENT = "#ff69b4"
FG = "white"
CIRCLE_R = 28
CIRCLE_GAP = 14


class BubbleManager:
    """Manages floating tkinter widgets beside the desktop pet."""

    def __init__(
        self,
        parent_hwnd: int,
        on_action: Callable[[str], None] | None = None,
        on_chat_submit: Callable[[str], None] | None = None,
    ) -> None:
        self._parent_hwnd = parent_hwnd
        self._on_action = on_action
        self._on_chat_submit = on_chat_submit
        self._pending_response: str | None = None

        self._root: tk.Tk | None = None
        self._input_win: tk.Toplevel | None = None
        self._entry: tk.Entry | None = None
        self._mode_win: tk.Toplevel | None = None
        self._bubbles: list[tk.Toplevel] = []

    def _ensure_root(self) -> None:
        if self._root is not None:
            return
        self._root = tk.Tk()
        # Hide root by making it tiny and placing it offscreen
        self._root.geometry("1x1+-100+-100")
        self._root.attributes("-alpha", 0)

    # ── input box ───────────────────────────────────────────────────

    def show_input(self, pet_rect: tuple[int, int, int, int]) -> None:
        self._destroy_input()
        self._ensure_root()
        x, y = _pos_input(pet_rect)

        self._input_win = tk.Toplevel(self._root)
        self._input_win.overrideredirect(True)
        self._input_win.attributes("-topmost", True)
        self._input_win.geometry(f"220x32+{x}+{y}")
        self._input_win.configure(bg=BG)
        self._input_win.bind("<Escape>", lambda _e: self._destroy_input())

        self._entry = tk.Entry(self._input_win, bg="#333", fg=FG, insertbackground=FG,
                               relief="flat", bd=4, font=("Segoe UI", 10))
        self._entry.pack(side="left", fill="x", expand=True, padx=(4, 2))
        self._entry.bind("<Return>", lambda _e: self._do_send())
        self._entry.after(80, self._entry.focus_force)

        btn = tk.Label(self._input_win, text="➤", fg=ACCENT, bg=BG,
                       font=("Segoe UI", 12, "bold"), cursor="hand2")
        btn.pack(side="right", padx=(0, 6))
        btn.bind("<Button-1>", lambda _e: self._do_send())

    # ── response bubble ─────────────────────────────────────────────

    def queue_response(self, text: str) -> None:
        self._pending_response = text

    def show_response(self, text: str, pet_rect: tuple[int, int, int, int]) -> None:
        self._ensure_root()
        x, y = _pos_bubble(pet_rect)

        w = min(280, max(140, len(text) * 8 + 40))
        h = 32 + (len(text) // 22 + 1) * 18

        win = tk.Toplevel(self._root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.configure(bg=BG)

        f = tk.Frame(win, bg=BG, padx=10, pady=8)
        f.pack(fill="both", expand=True)
        tk.Label(f, text=text, fg=FG, bg=BG, font=("Segoe UI", 10),
                 wraplength=w - 24, justify="left").pack()

        win.after(6000, win.destroy)
        self._bubbles.append(win)

    # ── mode balls ──────────────────────────────────────────────────

    def show_mode_bubble(self, pet_rect: tuple[int, int, int, int]) -> None:
        self._destroy_input()
        self._ensure_root()

        if self._mode_win is not None:
            try:
                self._mode_win.destroy()
            except Exception:
                pass

        x, y = _pos_mode(pet_rect)
        w = CIRCLE_R * 6 + CIRCLE_GAP * 2 + 20
        h = CIRCLE_R * 2 + 40

        self._mode_win = tk.Toplevel(self._root)
        self._mode_win.overrideredirect(True)
        self._mode_win.attributes("-topmost", True)
        self._mode_win.geometry(f"{w}x{h}+{x}+{y}")
        self._mode_win.configure(bg="")  # transparent-ish
        self._mode_win.attributes("-transparentcolor", "gray1")
        # We use a solid bg and draw circles on canvas

        canvas = tk.Canvas(self._mode_win, width=w, height=h,
                           bg="gray1", highlightthickness=0, bd=0)
        canvas.pack()

        modes = [
            ("sequential", "⭢", "顺序"),
            ("random", "↬", "随机"),
            ("repeat", "⟳", "循环"),
        ]
        item_data: list[tuple[int, str]] = []  # (item_id, mode_value)

        for i, (mode, symbol, label) in enumerate(modes):
            cx = 10 + CIRCLE_R + i * (CIRCLE_R * 2 + CIRCLE_GAP)
            cy = h // 2 - 6

            # Circle
            item = canvas.create_oval(
                cx - CIRCLE_R, cy - CIRCLE_R,
                cx + CIRCLE_R, cy + CIRCLE_R,
                fill="#2a2a2a", outline=ACCENT, width=2,
            )
            item_data.append((item, mode))

            # Symbol
            canvas.create_text(cx, cy - 4, text=symbol, fill=FG,
                               font=("Segoe UI", 18, "bold"))

            # Label
            canvas.create_text(cx, cy + CIRCLE_R + 12, text=label, fill="#aaaaaa",
                               font=("Segoe UI", 9))

        def on_click(event):
            for item_id, mode_val in item_data:
                overlap = canvas.find_overlapping(event.x, event.y, event.x, event.y)
                if item_id in overlap:
                    if self._on_action:
                        self._on_action(f"set_mode:{mode_val}")
                    self._mode_win.destroy()
                    self._mode_win = None
                    return

        canvas.bind("<Button-1>", on_click)

        # Hover highlight
        def on_motion(event):
            for item_id, _ in item_data:
                overlap = canvas.find_overlapping(event.x, event.y, event.x, event.y)
                if item_id in overlap:
                    canvas.itemconfig(item_id, fill="#444444")
                else:
                    canvas.itemconfig(item_id, fill="#2a2a2a")

        canvas.bind("<Motion>", on_motion)

        def _auto_hide():
            if self._mode_win:
                self._mode_win.destroy()
                self._mode_win = None
        self._mode_win.after(8000, _auto_hide)

    # ── lifecycle ───────────────────────────────────────────────────

    def update(self) -> None:
        if self._root is not None:
            try:
                self._root.update_idletasks()
                self._root.update()
            except Exception:
                pass

    def _do_send(self) -> None:
        if self._entry is None:
            return
        t = self._entry.get().strip()
        self._destroy_input()
        if t and self._on_chat_submit:
            self._on_chat_submit(t)

    def _destroy_input(self) -> None:
        if self._input_win is not None:
            try:
                self._input_win.destroy()
            except Exception:
                pass
            self._input_win = None
        self._entry = None


# ── positioning ─────────────────────────────────────────────────────

def _pos_input(pet: tuple[int, int, int, int]) -> tuple[int, int]:
    px, py, px2, py2 = pet
    try:
        import win32api; sw = win32api.GetSystemMetrics(0)
    except Exception:
        sw = 1920
    mid = sw // 2
    x = px2 + 8 if px < mid else px - 228
    y = py + 20
    if x < 4: x = 4
    if x + 220 > sw - 4: x = sw - 224
    return x, y


def _pos_bubble(pet: tuple[int, int, int, int]) -> tuple[int, int]:
    px, py, px2, py2 = pet
    try:
        import win32api; sw = win32api.GetSystemMetrics(0)
    except Exception:
        sw = 1920
    mid = sw // 2
    x = px2 + 8 if px < mid else px - 228
    y = py - 10
    if x < 4: x = 4
    return x, y


def _pos_mode(pet: tuple[int, int, int, int]) -> tuple[int, int]:
    px, py, px2, py2 = pet
    try:
        import win32api; sw = win32api.GetSystemMetrics(0)
    except Exception:
        sw = 1920
    mid = sw // 2
    x = px2 + 8 if px < mid else px - 228
    y = py - 40
    if x < 4: x = 4
    return x, y
