"""Shared constants and data used by both terminal UI widgets and desktop pet.

No Textual dependency — this module is safe to import from the pet without
pulling in the entire TUI framework.
"""

from __future__ import annotations

# ── Shimmer palettes ────────────────────────────────────────────────────

_SHIMMER_PALETTES: dict[str, list[str]] = {
    "pink":     ["#ff69b4", "#ff85c0", "#ff1493", "#ff6eb4", "#ffb6c1",
                 "#ff99cc", "#db7093", "#ff77aa", "#ff4da6", "#ff8da1"],
    "yellow":   ["#ffd700", "#ffec8b", "#ffdb58", "#ffe4b5", "#f0e68c",
                 "#eedd82", "#daa520", "#ffc125", "#fce883", "#fff8dc"],
    "red":      ["#ff4500", "#ff6347", "#dc143c", "#ff0000", "#cd5c5c",
                 "#f08080", "#e9967a", "#fa8072", "#ff6b6b", "#ee2c2c"],
    "blue":     ["#1e90ff", "#00bfff", "#87ceeb", "#4682b4", "#5f9ea0",
                 "#6495ed", "#4169e1", "#0000cd", "#00ced1", "#7ec8e3"],
    "purple":   ["#8b00ff", "#9932cc", "#ba55d3", "#da70d6", "#ee82ee",
                 "#dda0dd", "#ff00ff", "#8b008b", "#9400d3", "#9370db"],
    "green":    ["#00ff7f", "#3cb371", "#2e8b57", "#228b22", "#32cd32",
                 "#7cfc00", "#00fa9a", "#98fb98", "#90ee90", "#adff2f"],
    "orange":   ["#ff8c00", "#ffa500", "#ffb347", "#ffd700", "#ff7f50",
                 "#f4a460", "#d2691e", "#cd853f", "#ff6347", "#e59866"],
    "gray":     ["#b0b0b0", "#c0c0c0", "#d3d3d3", "#a9a9a9", "#808080",
                 "#696969", "#778899", "#e0e0e0", "#f5f5f5", "#bebebe"],
    "brown":    ["#8b4513", "#a0522d", "#d2b48c", "#deb887", "#f5deb3",
                 "#d2691e", "#b8860b", "#cd853f", "#8b7355", "#c4a882"],
    "white":    ["#ffffff"],
    "colorful": ["#ff69b4", "#ffd700", "#ff4500", "#1e90ff", "#8b00ff",
                 "#00ff7f", "#ff8c00", "#b0b0b0", "#8b4513", "#ffffff"],
}

_current_palette: str = "pink"
_SHIMMER_INTERVAL = 0.24


def set_shimmer_palette(name: str) -> bool:
    """Switch shimmer color palette. Returns True if valid name."""
    global _current_palette
    if name in _SHIMMER_PALETTES:
        _current_palette = name
        return True
    return False


def get_shimmer_palette() -> str:
    return _current_palette


# ── Mascot pixel-art data ────────────────────────────────────────────────

_MASCOT_COLS: int = 14
_MASCOT_ROWS: int = 7

_MASCOT_BODY: list[str] = [
    "......██......",
    "....██████....",
    "..██████████..",
    "██████████████",
    "..██████████..",
    "....██████....",
    "......██......",
]

_MASCOT_EYES: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {
    "center":        ((3, 5), (3, 8)),
    "up":            ((2, 5), (2, 8)),
    "down":          ((4, 5), (4, 8)),
    "left":          ((3, 3), (3, 6)),
    "right":         ((3, 7), (3, 10)),
    "top_left":      ((2, 4), (2, 7)),
    "top_right":     ((2, 6), (2, 9)),
    "bottom_left":   ((4, 4), (4, 7)),
    "bottom_right":  ((4, 6), (4, 9)),
}
