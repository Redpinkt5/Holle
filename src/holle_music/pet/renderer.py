"""MascotRenderer — renders the ASCII mascot as a transparent PNG using Pillow."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageColor

from holle_music.widgets import Mascot, _SHIMMER_PALETTES, _SHIMMER_INTERVAL, _current_palette


CELL_W: int = 10   # terminal char width
CELL_H: int = 20   # terminal char height (2x width for square aspect)
PADDING: int = 4
DEFAULT_BODY_COLOR: str = "#ffffff"


class MascotRenderer:
    """Render the ASCII mascot as an RGBA PNG image."""

    def render(self, direction: str, active: bool, palette_name: str = "pink", shimmer_idx: int = 0) -> Image.Image:
        """Generate RGBA mascot image.

        Args:
            direction: Eye direction (must be a key in ``Mascot._EYES``).
            active: Whether the mascot is in active/shimmer state.
            palette_name: Name of the shimmer palette theme.
            shimmer_idx: Index into the palette for the current color.

        Returns:
            A Pillow ``Image`` in RGBA mode with a transparent background.
        """
        width = Mascot.COLS * CELL_W + PADDING * 2
        height = Mascot.ROWS * CELL_H + PADDING * 2
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        if active:
            palette = _SHIMMER_PALETTES.get(palette_name, _SHIMMER_PALETTES["pink"])
            body_color = palette[shimmer_idx % len(palette)]
        else:
            body_color = DEFAULT_BODY_COLOR

        self._draw_body(draw, body_color, active)
        self._draw_eyes(draw, direction)

        return img

    def _draw_body(self, draw: ImageDraw.Draw, color: str, active: bool) -> None:
        """Draw diamond body from ASCII template."""
        for row_idx, row_str in enumerate(Mascot._BODY):
            for col_idx, ch in enumerate(row_str):
                if ch == "█":
                    x0 = PADDING + col_idx * CELL_W
                    y0 = PADDING + row_idx * CELL_H
                    x1 = x0 + CELL_W - 1
                    y1 = y0 + CELL_H - 1
                    draw.rectangle([x0, y0, x1, y1], fill=color)

    def _draw_eyes(self, draw: ImageDraw.Draw, direction: str) -> None:
        """Draw eyes at position for given direction."""
        (left_row, left_col), (right_row, right_col) = Mascot._EYES[direction]
        for row, col in ((left_row, left_col), (right_row, right_col)):
            x0 = PADDING + col * CELL_W
            y0 = PADDING + row * CELL_H
            x1 = x0 + CELL_W - 1
            y1 = y0 + CELL_H - 1
            # Solid black eye (no sclera)
            draw.rectangle([x0, y0, x1, y1], fill="#000000")
