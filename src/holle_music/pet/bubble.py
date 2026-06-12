"""BubbleManager — unified tkinter panel for mode switching and chat."""

from __future__ import annotations

import tkinter as tk
from typing import Callable


WIDTH = 320
HEIGHT = 280
BG_COLOR = "#252525"
TITLE_BG = "#1e1e1e"
INPUT_BG = "#333333"
ACCENT = "#ff69b4"
TEXT_COLOR = "white"


class BubbleManager:
    """A single tkinter window that hosts both mode-switch and chat panels."""

    def __init__(
        self,
        parent_hwnd: int,
        on_action: Callable[[str], None] | None = None,
        on_chat_submit: Callable[[str], None] | None = None,
    ) -> None:
        self._parent_hwnd = parent_hwnd
        self._on_action = on_action
        self._on_chat_submit = on_chat_submit
        self._messages: list[tuple[str, str]] = []

        self._tk_root: tk.Tk | None = None
        self._window: tk.Toplevel | None = None
        self._panel_frame: tk.Frame | None = None
        self._chat_text: tk.Text | None = None
        self._chat_entry: tk.Entry | None = None
        self._mode_var: tk.StringVar | None = None

        self._ensure_tk_root()

    def _ensure_tk_root(self) -> None:
        if self._tk_root is not None:
            return
        try:
            self._tk_root = tk.Tk()
            self._tk_root.withdraw()
        except Exception as e:
            print(f"[BUBBLE] Failed to create tkinter root: {e}")
            self._tk_root = None

    def show(self, pet_rect: tuple[int, int, int, int], panel: str = "chat") -> None:
        """Show the unified window near the pet."""
        if self._tk_root is None:
            print("[BUBBLE] Cannot show: tk_root is None")
            return

        try:
            self.hide()

            x, y = self._calc_position(pet_rect)
            print(f"[BUBBLE] Creating window at {x},{y} panel={panel}")

            self._window = tk.Toplevel(self._tk_root)
            self._window.overrideredirect(True)
            self._window.attributes("-topmost", True)
            self._window.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")
            self._window.configure(bg=BG_COLOR)
            self._window.bind("<Escape>", lambda _e: self.hide())
            self._window.deiconify()
            self._window.lift()

            self._build_title_bar()
            self._panel_frame = tk.Frame(self._window, bg=BG_COLOR)
            self._panel_frame.pack(fill="both", expand=True)

            if panel == "mode":
                self._build_mode_panel()
            else:
                self._build_chat_panel()

            self._make_draggable()
            self._window.update_idletasks()
            self._window.update()
            print("[BUBBLE] Window shown")
        except Exception as e:
            print(f"[BUBBLE] Show error: {e}")
            import traceback
            traceback.print_exc()

    def update(self) -> None:
        """Process pending tkinter events — called from Win32 message loop."""
        if self._tk_root is not None:
            try:
                self._tk_root.update_idletasks()
                self._tk_root.update()
            except Exception:
                pass

    def hide(self) -> None:
        """Hide the window."""
        if self._window is not None:
            try:
                self._window.destroy()
            except Exception:
                pass
            self._window = None
        self._panel_frame = None
        self._chat_text = None
        self._chat_entry = None
        self._mode_var = None

    def add_message(self, role: str, text: str) -> None:
        self._messages.append((role, text))
        while len(self._messages) > 50:
            self._messages.pop(0)

    def refresh_chat(self) -> None:
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
        self._chat_text.tag_config("user", foreground=ACCENT, font=("Segoe UI", 9, "bold"))
        self._chat_text.tag_config("ai", foreground="#aaaaaa", font=("Segoe UI", 9, "bold"))
        self._chat_text.tag_config("user_text", foreground="white")
        self._chat_text.tag_config("ai_text", foreground="white")
        self._chat_text.config(state="disabled")
        self._chat_text.see(tk.END)

    def _build_title_bar(self) -> None:
        title_frame = tk.Frame(self._window, bg=TITLE_BG, height=28)
        title_frame.pack(fill="x")
        title_frame.pack_propagate(False)

        tk.Label(
            title_frame,
            text="Holle Panel",
            fg=TEXT_COLOR,
            bg=TITLE_BG,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=8, pady=2)

        close_btn = tk.Label(
            title_frame,
            text="✕",
            fg="#ff4444",
            bg=TITLE_BG,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        )
        close_btn.pack(side="right", padx=8, pady=2)
        close_btn.bind("<Button-1>", lambda _e: self.hide())

        self._title_frame = title_frame

    def _build_mode_panel(self) -> None:
        frame = tk.Frame(self._panel_frame, bg=BG_COLOR)
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(
            frame,
            text="切换播放模式",
            fg=TEXT_COLOR,
            bg=BG_COLOR,
            font=("Segoe UI", 12, "bold"),
        ).pack(pady=(10, 20))

        modes = [
            ("sequential", "顺序播放 ⭢"),
            ("random", "随机播放 ↬"),
            ("repeat", "单曲循环 ⟳"),
        ]

        self._mode_var = tk.StringVar(value="sequential")
        for value, label in modes:
            btn = tk.Radiobutton(
                frame,
                text=label,
                variable=self._mode_var,
                value=value,
                indicatoron=0,
                bg="#333333",
                fg=TEXT_COLOR,
                selectcolor=ACCENT,
                activebackground="#444444",
                activeforeground=TEXT_COLOR,
                font=("Segoe UI", 11),
                cursor="hand2",
                width=16,
                pady=8,
            )
            btn.pack(pady=6)

        def apply():
            mode = self._mode_var.get() if self._mode_var else "sequential"
            if self._on_action:
                self._on_action(f"set_mode:{mode}")
            self.hide()

        tk.Button(
            frame,
            text="确认切换",
            command=apply,
            bg=ACCENT,
            fg=TEXT_COLOR,
            activebackground="#ff85c0",
            activeforeground=TEXT_COLOR,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            pady=6,
            width=16,
        ).pack(pady=(20, 0))

    def _build_chat_panel(self) -> None:
        frame = tk.Frame(self._panel_frame, bg=BG_COLOR)
        frame.pack(fill="both", expand=True)

        # Chat history
        self._chat_text = tk.Text(
            frame,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
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
        input_frame = tk.Frame(frame, bg=BG_COLOR)
        input_frame.pack(fill="x", padx=8, pady=8)

        self._chat_entry = tk.Entry(
            input_frame,
            bg=INPUT_BG,
            fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            relief="flat",
            bd=6,
            highlightthickness=0,
            font=("Segoe UI", 10),
        )
        self._chat_entry.pack(side="left", fill="x", expand=True)
        self._chat_entry.bind("<Return>", lambda _e: self._on_send())
        self._chat_entry.focus_force()

        send_btn = tk.Label(
            input_frame,
            text="➤",
            fg=ACCENT,
            bg=BG_COLOR,
            font=("Segoe UI", 12),
            cursor="hand2",
        )
        send_btn.pack(side="right", padx=(8, 0))
        send_btn.bind("<Button-1>", lambda _e: self._on_send())

        self.refresh_chat()

    def _on_send(self) -> None:
        if self._chat_entry is None:
            return
        text = self._chat_entry.get().strip()
        if not text:
            return
        self._chat_entry.delete(0, tk.END)
        self.add_message("user", text)
        self.refresh_chat()
        if self._on_chat_submit:
            self._on_chat_submit(text)
        elif self._on_action:
            self._on_action(f"chat:{text}")

    def _make_draggable(self) -> None:
        if self._window is None or self._title_frame is None:
            return
        self._drag_x = 0
        self._drag_y = 0

        def start(event):
            self._drag_x = event.x_root
            self._drag_y = event.y_root

        def move(event):
            dx = event.x_root - self._drag_x
            dy = event.y_root - self._drag_y
            self._drag_x = event.x_root
            self._drag_y = event.y_root
            if self._window is not None:
                self._window.geometry(f"+{self._window.winfo_x() + dx}+{self._window.winfo_y() + dy}")

        self._title_frame.bind("<Button-1>", start)
        self._title_frame.bind("<B1-Motion>", move)

    @staticmethod
    def _calc_position(pet_rect: tuple[int, int, int, int]) -> tuple[int, int]:
        px, py, px2, py2 = pet_rect
        cx = (px + px2) // 2

        try:
            import win32api
            screen_w = win32api.GetSystemMetrics(0)
            screen_h = win32api.GetSystemMetrics(1)
        except Exception:
            screen_w, screen_h = 1920, 1080

        # Default centered above pet
        x = cx - WIDTH // 2
        y = py - HEIGHT - 8

        # Flip below if off top
        if y < 0:
            y = py2 + 8

        # Clamp horizontally
        if x < 8:
            x = 8
        elif x + WIDTH > screen_w - 8:
            x = screen_w - WIDTH - 8

        # Prefer side placement near edges
        if px < WIDTH + 20:
            x = px2 + 10
            if x + WIDTH > screen_w - 8:
                x = screen_w - WIDTH - 8
        elif px2 > screen_w - WIDTH - 20:
            x = px - WIDTH - 10
            if x < 8:
                x = 8

        return x, y
