"""Floating tkinter chat window for the desktop pet."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import font as tkfont
from typing import Callable

from holle_music.minimax_api import MiniMaxService


WIDTH = 320
HEIGHT = 240
BG_COLOR = "#1e1e1e"
TEXT_COLOR = "#ffffff"
USER_BUBBLE = "#ff69b4"
AI_BUBBLE = "#3d3d3d"
MAX_MESSAGES = 20


class ChatDialog:
    """Floating frameless chat window."""

    def __init__(self) -> None:
        self._window: tk.Toplevel | None = None
        self._canvas: tk.Canvas | None = None
        self._scrollable_frame: tk.Frame | None = None
        self._entry: tk.Entry | None = None
        self._service = MiniMaxService()
        self._messages: list[tuple[str, str]] = []  # (role, text)
        self._pending_ai = False

    # ── Public API ────────────────────────────────────────────────────────

    def show(self, x: int, y: int) -> None:
        """Show dialog at screen position (x, y)."""
        if self._window is not None and self._window.winfo_exists():
            self._window.lift()
            return

        self._build_window(x, y)

    def hide(self) -> None:
        """Close the dialog."""
        if self._window is not None and self._window.winfo_exists():
            self._window.destroy()
        self._window = None
        self._canvas = None
        self._scrollable_frame = None
        self._entry = None

    # ── Window construction ───────────────────────────────────────────────

    def _build_window(self, x: int, y: int) -> None:
        self._window = tk.Toplevel()
        self._window.overrideredirect(True)
        self._window.attributes("-topmost", True)
        self._window.configure(bg=BG_COLOR)
        self._window.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")

        # Close on Escape
        self._window.bind("<Escape>", lambda _e: self.hide())
        # Close on click outside — defer so current click doesn't close immediately
        self._window.after(100, self._bind_outside_click)

        # Main layout
        self._window.rowconfigure(0, weight=1)
        self._window.rowconfigure(1, weight=0)
        self._window.columnconfigure(0, weight=1)

        # ── Messages area (scrollable canvas) ──
        self._canvas = tk.Canvas(
            self._window,
            bg=BG_COLOR,
            highlightthickness=0,
            bd=0,
        )
        self._canvas.grid(row=0, column=0, sticky="nsew", padx=4, pady=(4, 0))

        scrollbar = tk.Scrollbar(
            self._window,
            orient="vertical",
            command=self._canvas.yview,
            bg=BG_COLOR,
            troughcolor=BG_COLOR,
        )
        scrollbar.grid(row=0, column=1, sticky="ns", pady=(4, 0))
        self._canvas.configure(yscrollcommand=scrollbar.set)

        self._scrollable_frame = tk.Frame(self._canvas, bg=BG_COLOR)
        self._canvas_window = self._canvas.create_window(
            (0, 0),
            window=self._scrollable_frame,
            anchor="nw",
            width=WIDTH - 8,
        )

        self._scrollable_frame.bind(
            "<Configure>",
            lambda _e: self._canvas.configure(
                scrollregion=self._canvas.bbox("all")
            ),
        )
        self._canvas.bind(
            "<Configure>",
            lambda _e: self._canvas.itemconfig(
                self._canvas_window, width=_e.width
            ),
        )

        # ── Input area ──
        input_frame = tk.Frame(self._window, bg=BG_COLOR)
        input_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        input_frame.columnconfigure(0, weight=1)

        self._entry = tk.Entry(
            input_frame,
            bg="#2d2d2d",
            fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            relief="flat",
            bd=4,
            highlightthickness=0,
            font=("Segoe UI", 10),
        )
        self._entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self._entry.bind("<Return>", lambda _e: self._on_send())
        self._entry.focus_set()

        send_btn = tk.Label(
            input_frame,
            text="➤",
            fg=USER_BUBBLE,
            bg=BG_COLOR,
            font=("Segoe UI", 12),
            cursor="hand2",
        )
        send_btn.grid(row=0, column=1)
        send_btn.bind("<Button-1>", lambda _e: self._on_send())

        # Redraw existing messages (if any from previous show)
        self._redraw_messages()

    def _bind_outside_click(self) -> None:
        if self._window is None or not self._window.winfo_exists():
            return
        self._window.bind("<Button-1>", self._on_window_click)
        # Also bind to all child widgets so clicks on them don't propagate
        for widget in self._window.winfo_children():
            widget.bind("<Button-1>", self._on_window_click)
            for child in widget.winfo_children():
                child.bind("<Button-1>", self._on_window_click)

    def _on_window_click(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        # If the click target is inside the window, do nothing.
        # If it's somehow outside (shouldn't happen for Toplevel), close.
        widget = event.widget
        try:
            # Check if widget is descendant of our window
            if widget == self._window:
                return
            parent = widget.winfo_toplevel()
            if parent == self._window:
                return
        except tk.TclError:
            pass
        self.hide()

    # ── Message handling ──────────────────────────────────────────────────

    def _add_message(self, role: str, text: str) -> None:
        self._messages.append((role, text))
        while len(self._messages) > MAX_MESSAGES:
            self._messages.pop(0)
        if self._scrollable_frame is not None and self._scrollable_frame.winfo_exists():
            self._render_bubble(role, text)
            self._scroll_to_bottom()

    def _redraw_messages(self) -> None:
        if self._scrollable_frame is None:
            return
        for widget in self._scrollable_frame.winfo_children():
            widget.destroy()
        for role, text in self._messages:
            self._render_bubble(role, text)
        self._scroll_to_bottom()

    def _render_bubble(self, role: str, text: str) -> None:
        if self._scrollable_frame is None:
            return

        is_user = role == "user"
        bubble_color = USER_BUBBLE if is_user else AI_BUBBLE
        anchor = "e" if is_user else "w"
        side = tk.RIGHT if is_user else tk.LEFT

        # Outer frame for alignment
        outer = tk.Frame(self._scrollable_frame, bg=BG_COLOR)
        outer.pack(fill="x", padx=4, pady=2)

        # Bubble frame
        bubble = tk.Frame(outer, bg=bubble_color, bd=0)
        bubble.pack(side=side)

        # Message label (wrap text)
        label = tk.Label(
            bubble,
            text=text,
            bg=bubble_color,
            fg=TEXT_COLOR,
            font=("Segoe UI", 10),
            wraplength=WIDTH - 40,
            justify=tk.LEFT if not is_user else tk.RIGHT,
            padx=8,
            pady=4,
        )
        label.pack()

    def _scroll_to_bottom(self) -> None:
        if self._canvas is not None and self._canvas.winfo_exists():
            self._canvas.update_idletasks()
            self._canvas.yview_moveto(1.0)

    # ── Send / AI reply ───────────────────────────────────────────────────

    def _on_send(self) -> None:
        if self._entry is None or not self._entry.winfo_exists():
            return
        text = self._entry.get().strip()
        if not text:
            return
        self._entry.delete(0, tk.END)

        self._add_message("user", text)

        if self._pending_ai:
            return
        self._pending_ai = True

        # Run AI in background thread
        thread = threading.Thread(
            target=self._ai_worker,
            args=(text,),
            daemon=True,
        )
        thread.start()

    def _ai_worker(self, text: str) -> None:
        try:
            reply = self._service.chat(text)
        except Exception as exc:
            reply = f"Error: {exc}"

        # Schedule UI update on main thread
        if self._window is not None and self._window.winfo_exists():
            self._window.after(0, lambda: self._on_ai_reply(reply))

    def _on_ai_reply(self, reply: str) -> None:
        self._pending_ai = False
        self._add_message("ai", reply)
