#!/usr/bin/env python3
"""纯终端极简播放器控制 UI — 全部使用 █ 字符拼接，标准库 only.

运行方式: python terminal_controls.py
按键: ← 上一曲 | 空格 播放/暂停 | → 下一曲 | q 退出
"""

import os
import sys
import shutil
from typing import Literal

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import msvcrt
else:
    import select
    import termios
    import tty

# ── 按钮形状（11 行，█ 紧密拼接）────────────────────────────────────

PREV = [
    "          █",
    "        ███",
    "      █████",
    "    ███████",
    "  █████████",
    "███████████",
    "  █████████",
    "    ███████",
    "      █████",
    "        ███",
    "          █",
]

NEXT = [
    "█          ",
    "███        ",
    "█████      ",
    "███████    ",
    "█████████  ",
    "███████████",
    "█████████  ",
    "███████    ",
    "█████      ",
    "███        ",
    "█          ",
]

PLAY = [
    "          █",
    "        █████",
    "      █████████",
    "    █████████████",
    "  █████████████████",
    "█████████████████████",
    "  █████████████████",
    "    █████████████",
    "      █████████",
    "        █████",
    "          █",
]

PAUSE = [
    "    ████     ████    ",
    "    ████     ████    ",
    "    ████     ████    ",
    "    ████     ████    ",
    "    ████     ████    ",
    "    ████     ████    ",
    "    ████     ████    ",
    "    ████     ████    ",
    "    ████     ████    ",
    "    ████     ████    ",
    "    ████     ████    ",
]

SHAPE_HEIGHT = 11


# ── 终端控制 ─────────────────────────────────────────────────────────

def hide_cursor() -> None:
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()


def show_cursor() -> None:
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()


def clear_screen() -> None:
    sys.stdout.write("\033[2J")
    sys.stdout.flush()


def move_cursor(row: int, col: int) -> None:
    sys.stdout.write(f"\033[{row};{col}H")
    sys.stdout.flush()


def enable_raw_mode() -> object:
    if IS_WINDOWS:
        return None  # Windows 无需设置
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setraw(fd)
    return old


def restore_terminal(old: object) -> None:
    if IS_WINDOWS:
        return
    if old is not None:
        fd = sys.stdin.fileno()
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def get_key() -> str | None:
    """非阻塞读取按键。"""
    if IS_WINDOWS:
        if not msvcrt.kbhit():
            return None
        ch = msvcrt.getch()
        if ch in (b"\x00", b"\xe0"):
            ch2 = msvcrt.getch()
            return _win_arrow(ch2)
        try:
            return ch.decode("utf-8", errors="replace")
        except Exception:
            return None
    else:
        if not select.select([sys.stdin], [], [], 0.05)[0]:
            return None
        data = os.read(sys.stdin.fileno(), 8)
        return data.decode("utf-8", errors="replace")


def _win_arrow(code: bytes) -> str:
    """Windows 方向键扫描码 -> 方向标识。"""
    mapping = {
        b"H": "up",
        b"P": "down",
        b"K": "left",
        b"M": "right",
    }
    return mapping.get(code, "")


def parse_key(data: str | None) -> str | None:
    if not data:
        return None
    if data in ("\x1b[A", "up"):
        return "up"
    if data in ("\x1b[B", "down"):
        return "down"
    if data in ("\x1b[C", "right"):
        return "right"
    if data in ("\x1b[D", "left"):
        return "left"
    if data == " ":
        return "space"
    if data in ("q", "Q", "\x03"):
        return "quit"
    return None


# ── 形状宽度 ─────────────────────────────────────────────────────────

def _max_width(shape: list[str]) -> int:
    return max(len(line) for line in shape)

PREV_WIDTH = _max_width(PREV)
NEXT_WIDTH = _max_width(NEXT)
PLAY_WIDTH = _max_width(PLAY)
PAUSE_WIDTH = _max_width(PAUSE)


# ── 布局计算 ─────────────────────────────────────────────────────────

def calc_layout() -> dict:
    size = shutil.get_terminal_size()
    term_w = max(size.columns, 60)
    term_h = max(size.lines, 18)

    mid_w = max(PLAY_WIDTH, PAUSE_WIDTH)
    total_w = PREV_WIDTH + mid_w + NEXT_WIDTH
    gap = max(4, (term_w - total_w) // 4)
    margin_left = max(1, (term_w - total_w - gap * 2) // 2)
    top = max(1, (term_h - SHAPE_HEIGHT) // 2)

    return {
        "term_w": term_w,
        "term_h": term_h,
        "top": top,
        "gap": gap,
        "prev_col": margin_left + 1,
        "mid_col": margin_left + PREV_WIDTH + gap + 1,
        "next_col": margin_left + PREV_WIDTH + gap + mid_w + gap + 1,
    }


# ── 渲染 ─────────────────────────────────────────────────────────────

WHITE = "\033[97m"
RESET = "\033[0m"


def _draw_shape(row: int, col: int, shape: list[str]) -> None:
    move_cursor(row, col)
    sys.stdout.write(f"{WHITE}{shape[row - 1]}{RESET}")


def draw_all(playing: bool, layout: dict) -> None:
    top = layout["top"]
    middle_shape = PAUSE if playing else PLAY

    clear_screen()
    for r in range(SHAPE_HEIGHT):
        row = top + r
        _draw_shape(row, layout["prev_col"], PREV)
        _draw_shape(row, layout["mid_col"], middle_shape)
        _draw_shape(row, layout["next_col"], NEXT)
    sys.stdout.flush()


def draw_middle(playing: bool, layout: dict) -> None:
    top = layout["top"]
    col = layout["mid_col"]
    shape = PAUSE if playing else PLAY

    for r in range(SHAPE_HEIGHT):
        _draw_shape(top + r, col, shape)
    sys.stdout.flush()


# ── 主循环 ───────────────────────────────────────────────────────────

def main() -> None:
    playing = False
    layout = calc_layout()

    old_tty = enable_raw_mode()
    try:
        hide_cursor()
        draw_all(playing, layout)

        while True:
            key = parse_key(get_key())
            if key is None:
                continue

            if key == "quit":
                break

            new_playing = playing
            if key == "space":
                new_playing = not playing
            elif key == "left":
                sys.stdout.write("\a")
            elif key == "right":
                sys.stdout.write("\a")

            if new_playing != playing:
                playing = new_playing
                draw_middle(playing, layout)

    finally:
        restore_terminal(old_tty)
        show_cursor()
        move_cursor(layout["term_h"], 1)
        print()


if __name__ == "__main__":
    main()
