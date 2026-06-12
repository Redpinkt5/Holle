"""BubbleManager — tkinter panel for mode switching and chat, positioned beside the pet."""

from __future__ import annotations

import tkinter as tk
from typing import Callable


WIDTH = 300
HEIGHT = 260
GAP = 12
BG = "#1e1e1e"
INP = "#2d2d2d"
ACC = "#ff69b4"
FG = "white"


class BubbleManager:
    """Displays a panel near the desktop pet for mode switching or chat."""

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

        self._win: tk.Tk | None = None
        self._chat_text: tk.Text | None = None
        self._chat_entry: tk.Entry | None = None
        self._mode_var: tk.StringVar | None = None

    def show(self, pet_rect: tuple[int, int, int, int], panel: str = "chat") -> None:
        try:
            self.hide()
            x, y = _pos(WIDTH, HEIGHT, pet_rect)

            self._win = tk.Tk()
            self._win.overrideredirect(True)
            self._win.attributes("-topmost", True)
            self._win.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")
            self._win.configure(bg=BG)
            self._win.bind("<Escape>", lambda _e: self.hide())

            # Title bar
            title = tk.Frame(self._win, bg="#141414", height=26)
            title.pack(fill="x")
            title.pack_propagate(False)
            tk.Label(title, text="Holle Panel", fg=FG, bg="#141414",
                     font=("Segoe UI", 9, "bold")).pack(side="left", padx=8)
            x_btn = tk.Label(title, text="✕", fg="#ff4444", bg="#141414",
                             font=("Segoe UI", 10, "bold"), cursor="hand2")
            x_btn.pack(side="right", padx=8)
            x_btn.bind("<Button-1>", lambda _e: self.hide())

            # Make draggable
            dx = [0]; dy = [0]
            def _s(e): dx[0], dy[0] = e.x_root, e.y_root
            def _m(e):
                nx, ny = e.x_root - dx[0], e.y_root - dy[0]
                dx[0], dy[0] = e.x_root, e.y_root
                self._win.geometry(f"+{self._win.winfo_x() + nx}+{self._win.winfo_y() + ny}")
            title.bind("<Button-1>", _s)
            title.bind("<B1-Motion>", _m)

            # Body
            body = tk.Frame(self._win, bg=BG)
            body.pack(fill="both", expand=True)

            if panel == "mode":
                self._build_mode(body)
            else:
                self._build_chat(body)

        except Exception as e:
            print(f"[BUBBLE] show: {e}")
            import traceback; traceback.print_exc()

    def update(self) -> None:
        if self._win is not None:
            try:
                self._win.update_idletasks()
                self._win.update()
            except Exception:
                pass

    def hide(self) -> None:
        if self._win is not None:
            try:
                self._win.destroy()
            except Exception:
                pass
            self._win = None
        self._chat_text = None
        self._chat_entry = None
        self._mode_var = None

    def add_message(self, role: str, text: str) -> None:
        self._messages.append((role, text))
        while len(self._messages) > 50:
            self._messages.pop(0)

    def refresh_chat(self) -> None:
        if not self._chat_text:
            return
        self._chat_text.config(state="normal")
        self._chat_text.delete("1.0", tk.END)
        for role, text in self._messages:
            if role == "user":
                self._chat_text.insert(tk.END, "你: ", ("hdr_u",))
                self._chat_text.insert(tk.END, f"{text}\n", ("txt_u",))
            elif role == "ai":
                self._chat_text.insert(tk.END, "AI: ", ("hdr_a",))
                self._chat_text.insert(tk.END, f"{text}\n\n", ("txt_a",))
        for tag, fg, font in [("hdr_u", ACC, ("Segoe UI", 9, "bold")),
                               ("hdr_a", "#aaaaaa", ("Segoe UI", 9, "bold")),
                               ("txt_u", FG, None), ("txt_a", FG, None)]:
            kwargs = {"foreground": fg}
            if font: kwargs["font"] = font
            self._chat_text.tag_config(tag, **kwargs)
        self._chat_text.config(state="disabled")
        self._chat_text.see(tk.END)

    # ── panels ─────────────────────────────────────────────────────

    def _build_mode(self, parent: tk.Frame) -> None:
        tk.Label(parent, text="切换播放模式", fg=FG, bg=BG,
                 font=("Segoe UI", 11, "bold")).pack(pady=(12, 14))
        modes = [("sequential", "⭢ 顺序播放"), ("random", "↬ 随机播放"), ("repeat", "⟳ 单曲循环")]
        self._mode_var = tk.StringVar(value="sequential")
        for val, label in modes:
            tk.Radiobutton(parent, text=label, variable=self._mode_var, value=val,
                           indicatoron=0, bg="#333", fg=FG, selectcolor=ACC,
                           font=("Segoe UI", 11), cursor="hand2", width=14, pady=7).pack(pady=4)
        def _ok():
            if self._on_action:
                self._on_action(f"set_mode:{self._mode_var.get()}" if self._mode_var else "set_mode:sequential")
            self.hide()
        tk.Button(parent, text="确认", command=_ok, bg=ACC, fg=FG, font=("Segoe UI", 10, "bold"),
                  relief="flat", pady=6, width=14).pack(pady=(16, 0))

    def _build_chat(self, parent: tk.Frame) -> None:
        self._chat_text = tk.Text(parent, bg=BG, fg=FG, font=("Segoe UI", 10),
                                  wrap="word", state="disabled", relief="flat",
                                  padx=8, pady=6, highlightthickness=0, bd=0)
        self._chat_text.pack(fill="both", expand=True)
        bar = tk.Frame(parent, bg=BG)
        bar.pack(fill="x", padx=6, pady=6)
        self._chat_entry = tk.Entry(bar, bg=INP, fg=FG, insertbackground=FG,
                                    relief="flat", bd=5, highlightthickness=0,
                                    font=("Segoe UI", 10))
        self._chat_entry.pack(side="left", fill="x", expand=True)
        self._chat_entry.bind("<Return>", lambda _e: self._send())
        tk.Label(bar, text="发送", fg=ACC, bg=BG, font=("Segoe UI", 10, "bold"),
                 cursor="hand2").pack(side="right", padx=(6, 0))
        self.refresh_chat()
        self._win.after(100, self._chat_entry.focus_set)

    def _send(self) -> None:
        if not self._chat_entry:
            return
        t = self._chat_entry.get().strip()
        if not t:
            return
        self._chat_entry.delete(0, tk.END)
        self.add_message("user", t)
        self.refresh_chat()
        if self._on_chat_submit:
            self._on_chat_submit(t)


def _pos(w: int, h: int, pet: tuple[int, int, int, int]) -> tuple[int, int]:
    px, py, px2, py2 = pet
    try:
        import win32api
        sw = win32api.GetSystemMetrics(0)
        sh = win32api.GetSystemMetrics(1)
    except Exception:
        sw, sh = 1920, 1080

    mid = sw // 2
    x = px2 + GAP if px < mid else px - w - GAP
    y = ((py + py2) // 2) - h // 2

    if x + w > sw - 4: x = sw - w - 4
    if x < 4: x = 4
    if y < 4: y = 4
    if y + h > sh - 4: y = sh - h - 4
    return x, y
