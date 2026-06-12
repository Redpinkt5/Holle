"""BubbleManager — tkinter panel for mode switching and chat, positioned beside the pet."""

from __future__ import annotations

import tkinter as tk
from typing import Callable


WIDTH = 300
HEIGHT = 260
GAP = 12
BG_COLOR = "#1e1e1e"
INPUT_BG = "#2d2d2d"
ACCENT = "#ff69b4"
TEXT_COLOR = "white"


class BubbleManager:
    """A tkinter window that appears beside the desktop pet."""

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

        self._root: tk.Tk | None = None
        self._window: tk.Toplevel | None = None
        self._chat_text: tk.Text | None = None
        self._chat_entry: tk.Entry | None = None
        self._mode_var: tk.StringVar | None = None

        self._ensure_root()

    def _ensure_root(self) -> None:
        if self._root is not None:
            return
        try:
            self._root = tk.Tk()
            self._root.withdraw()
        except Exception as e:
            print(f"[BUBBLE] Tk root failed: {e}")

    def show(self, pet_rect: tuple[int, int, int, int], panel: str = "chat") -> None:
        if self._root is None:
            return
        try:
            self.hide()
            x, y = _calc_position(WIDTH, HEIGHT, pet_rect)

            self._window = tk.Toplevel(self._root)
            self._window.overrideredirect(True)
            self._window.attributes("-topmost", True)
            self._window.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")
            self._window.configure(bg=BG_COLOR)

            # Title bar
            title = tk.Frame(self._window, bg="#141414", height=26)
            title.pack(fill="x")
            title.pack_propagate(False)
            tk.Label(title, text="Holle Panel", fg=TEXT_COLOR, bg="#141414",
                     font=("Segoe UI", 9, "bold")).pack(side="left", padx=8)
            close = tk.Label(title, text="✕", fg="#ff4444", bg="#141414",
                             font=("Segoe UI", 10, "bold"), cursor="hand2")
            close.pack(side="right", padx=8)
            close.bind("<Button-1>", lambda _e: self.hide())

            body = tk.Frame(self._window, bg=BG_COLOR)
            body.pack(fill="both", expand=True)

            if panel == "mode":
                self._build_mode_panel(body)
            else:
                self._build_chat_panel(body)

            self._make_draggable(title)
            self._window.deiconify()
            self._window.lift()
            self._force_focus()

        except Exception as e:
            print(f"[BUBBLE] show error: {e}")
            import traceback
            traceback.print_exc()

    def update(self) -> None:
        """Process tkinter events — called each frame from Win32 loop."""
        if self._root is not None:
            try:
                self._root.update_idletasks()
                self._root.update()
            except Exception:
                pass

    def hide(self) -> None:
        if self._window is not None:
            try:
                self._window.destroy()
            except Exception:
                pass
            self._window = None
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
                self._chat_text.insert(tk.END, "你: ", ("user",))
                self._chat_text.insert(tk.END, f"{text}\n", ("user_txt",))
            elif role == "ai":
                self._chat_text.insert(tk.END, "AI: ", ("ai",))
                self._chat_text.insert(tk.END, f"{text}\n\n", ("ai_txt",))
        self._chat_text.tag_config("user", foreground=ACCENT, font=("Segoe UI", 9, "bold"))
        self._chat_text.tag_config("ai", foreground="#aaaaaa", font=("Segoe UI", 9, "bold"))
        self._chat_text.tag_config("user_txt", foreground="white")
        self._chat_text.tag_config("ai_txt", foreground="white")
        self._chat_text.config(state="disabled")
        self._chat_text.see(tk.END)

    # ── Mode panel ──────────────────────────────────────────────────────

    def _build_mode_panel(self, parent: tk.Frame) -> None:
        tk.Label(parent, text="切换播放模式", fg=TEXT_COLOR, bg=BG_COLOR,
                 font=("Segoe UI", 11, "bold")).pack(pady=(12, 14))

        modes = [
            ("sequential", "⭢ 顺序播放"),
            ("random", "↬ 随机播放"),
            ("repeat", "⟳ 单曲循环"),
        ]
        self._mode_var = tk.StringVar(value="sequential")
        for val, label in modes:
            rb = tk.Radiobutton(
                parent, text=label, variable=self._mode_var, value=val,
                indicatoron=0, bg="#333333", fg=TEXT_COLOR, selectcolor=ACCENT,
                font=("Segoe UI", 11), cursor="hand2", width=14, pady=7,
            )
            rb.pack(pady=4)

        def apply():
            mode = self._mode_var.get() if self._mode_var else "sequential"
            if self._on_action:
                self._on_action(f"set_mode:{mode}")
            self.hide()

        tk.Button(
            parent, text="确认", command=apply, bg=ACCENT, fg=TEXT_COLOR,
            font=("Segoe UI", 10, "bold"), relief="flat", pady=6, width=14,
        ).pack(pady=(16, 0))

    # ── Chat panel ──────────────────────────────────────────────────────

    def _build_chat_panel(self, parent: tk.Frame) -> None:
        self._chat_text = tk.Text(
            parent, bg=BG_COLOR, fg=TEXT_COLOR, font=("Segoe UI", 10),
            wrap="word", state="disabled", relief="flat",
            padx=8, pady=6, highlightthickness=0, bd=0,
        )
        self._chat_text.pack(fill="both", expand=True)

        bar = tk.Frame(parent, bg=BG_COLOR)
        bar.pack(fill="x", padx=6, pady=6)

        self._chat_entry = tk.Entry(
            bar, bg=INPUT_BG, fg=TEXT_COLOR, insertbackground=TEXT_COLOR,
            relief="flat", bd=5, highlightthickness=0, font=("Segoe UI", 10),
        )
        self._chat_entry.pack(side="left", fill="x", expand=True)
        self._chat_entry.bind("<Return>", lambda _e: self._on_send())

        tk.Label(bar, text="发送", fg=ACCENT, bg=BG_COLOR,
                 font=("Segoe UI", 10, "bold"), cursor="hand2"
                 ).pack(side="right", padx=(6, 0))

        self.refresh_chat()
        self._chat_entry.after(100, self._focus_entry)

    def _focus_entry(self) -> None:
        """Give focus to the entry widget after the window is ready."""
        if self._chat_entry is not None:
            self._chat_entry.focus_set()

    def _force_focus(self) -> None:
        """Use Win32 to bring the tkinter window to front for keyboard input."""
        if self._window is None:
            return
        try:
            import ctypes
            hwnd = self._window.winfo_id()
            ctypes.windll.user32.SetWindowPos(
                hwnd, -1, 0, 0, 0, 0, 0x0002 | 0x0001)  # HWND_TOPMOST | SWP_NOMOVE | SWP_NOSIZE
        except Exception:
            pass

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

    def _make_draggable(self, title: tk.Frame) -> None:
        dx = [0]
        dy = [0]

        def start(e):
            dx[0] = e.x_root
            dy[0] = e.y_root

        def move(e):
            nx = e.x_root - dx[0]
            ny = e.y_root - dy[0]
            dx[0] = e.x_root
            dy[0] = e.y_root
            if self._window:
                g = self._window.geometry()
                new_g = f"+{self._window.winfo_x() + nx}+{self._window.winfo_y() + ny}"
                self._window.geometry(new_g)

        title.bind("<Button-1>", start)
        title.bind("<B1-Motion>", move)


# ── Position helper ──────────────────────────────────────────────────────

def _calc_position(w: int, h: int, pet_rect: tuple[int, int, int, int]) -> tuple[int, int]:
    """Place beside or above the pet, avoiding screen edges."""
    px, py, px2, py2 = pet_rect
    pet_w = px2 - px
    pet_h = py2 - py
    pet_cx = (px + px2) // 2
    pet_cy = (py + py2) // 2

    try:
        import win32api
        sw = win32api.GetSystemMetrics(0)
        sh = win32api.GetSystemMetrics(1)
    except Exception:
        sw, sh = 1920, 1080

    mid_x = sw // 2

    if px < mid_x:
        # Pet on LEFT half → bubble on RIGHT side
        x = px2 + GAP
    else:
        # Pet on RIGHT half → bubble on LEFT side
        x = px - w - GAP

    # Vertically center with pet
    y = pet_cy - h // 2

    # Clamp within screen
    if x + w > sw - 4:
        x = sw - w - 4
    if x < 4:
        x = 4
    if y < 4:
        y = 4
    if y + h > sh - 4:
        y = sh - h - 4

    return x, y
