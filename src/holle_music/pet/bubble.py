"""Bubble system — floating input box and speech bubbles beside the desktop pet."""

from __future__ import annotations

import threading
import time
import tkinter as tk
from typing import Callable

BG = "#1e1e1e"
ACCENT = "#ff69b4"
FG = "white"


class BubbleManager:
    """Shows an input box on bottom-click, and speech bubbles for AI replies."""

    def __init__(
        self,
        parent_hwnd: int,
        on_action: Callable[[str], None] | None = None,
        on_chat_submit: Callable[[str], None] | None = None,
    ) -> None:
        self._parent_hwnd = parent_hwnd
        self._on_action = on_action
        self._on_chat_submit = on_chat_submit
        self._input_win: tk.Tk | None = None
        self._entry: tk.Entry | None = None
        self._bubbles: list[tk.Tk] = []
        self._pending_response: str | None = None

    def show_input(self, pet_rect: tuple[int, int, int, int]) -> None:
        """Show a tiny input box beside the pet."""
        self._destroy_input()
        x, y = _pos_input(pet_rect)

        self._input_win = tk.Tk()
        self._input_win.overrideredirect(True)
        self._input_win.attributes("-topmost", True)
        self._input_win.geometry(f"220x32+{x}+{y}")
        self._input_win.configure(bg=BG)
        self._input_win.bind("<Escape>", lambda _e: self._destroy_input())
        self._input_win.bind("<FocusOut>", lambda _e: self._destroy_input())

        self._entry = tk.Entry(
            self._input_win, bg="#333", fg=FG, insertbackground=FG,
            relief="flat", bd=4, font=("Segoe UI", 10),
        )
        self._entry.pack(side="left", fill="x", expand=True, padx=(4, 2))
        self._entry.bind("<Return>", lambda _e: self._do_send())
        self._entry.after(50, self._entry.focus_force)

        btn = tk.Label(self._input_win, text="➤", fg=ACCENT, bg=BG,
                       font=("Segoe UI", 12, "bold"), cursor="hand2")
        btn.pack(side="right", padx=(0, 6))
        btn.bind("<Button-1>", lambda _e: self._do_send())

    def queue_response(self, text: str) -> None:
        """Queue a response to show in main thread."""
        self._pending_response = text

    def show_response(self, text: str, pet_rect: tuple[int, int, int, int]) -> None:
        """Show a speech bubble with AI response beside the pet. Auto-hides."""
        self._destroy_input()
        x, y = _pos_bubble(pet_rect)

        w = min(260, max(160, len(text) * 8 + 40))
        h = 36 + (len(text) // 20 + 1) * 18

        win = tk.Tk()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.configure(bg=BG)

        # Rounded-ish look with a frame
        f = tk.Frame(win, bg=BG, padx=10, pady=8)
        f.pack(fill="both", expand=True)

        tk.Label(f, text=text, fg=FG, bg=BG, font=("Segoe UI", 10),
                 wraplength=w - 24, justify="left").pack()

        # Auto-hide
        win.after(5000, win.destroy)
        self._bubbles.append(win)

    def show_mode_bubble(self, pet_rect: tuple[int, int, int, int]) -> None:
        """Show a mode-switch bubble."""
        self._destroy_input()
        x, y = _pos_bubble(pet_rect)

        win = tk.Tk()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.geometry(f"180x120+{x}+{y}")
        win.configure(bg=BG)

        f = tk.Frame(win, bg=BG, padx=12, pady=10)
        f.pack(fill="both", expand=True)

        for mode, label in [("sequential", "⭢ 顺序"), ("random", "↬ 随机"), ("repeat", "⟳ 循环")]:
            def _set(m=mode, w=win):
                if self._on_action:
                    self._on_action(f"set_mode:{m}")
                w.destroy()
            tk.Button(f, text=label, command=_set, bg="#333", fg=FG,
                      font=("Segoe UI", 10), relief="flat", cursor="hand2",
                      width=10, pady=4).pack(pady=2)

        win.after(8000, win.destroy)
        self._bubbles.append(win)

    def update(self) -> None:
        """Process tkinter events."""
        for win in [self._input_win] + self._bubbles:
            if win is not None:
                try:
                    win.update_idletasks()
                    win.update()
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


def _pos_input(pet: tuple[int, int, int, int]) -> tuple[int, int]:
    px, py, px2, py2 = pet
    try:
        import win32api
        sw = win32api.GetSystemMetrics(0)
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
        import win32api
        sw = win32api.GetSystemMetrics(0)
    except Exception:
        sw = 1920
    mid = sw // 2
    x = px2 + 8 if px < mid else px - 228
    y = py - 10
    if x < 4: x = 4
    return x, y
