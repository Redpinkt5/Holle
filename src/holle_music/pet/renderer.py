"""MascotRenderer — renders the ASCII mascot as a transparent PNG using Pillow."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageColor

from holle_music.widgets import Mascot


CELL_SIZE: int = 14
PADDING: int = 4
DEFAULT_BODY_COLOR: str = "#ff69b4"


class MascotRenderer:
    """Render the ASCII mascot as an RGBA PNG image."""

    def render(self, direction: str, active: bool, shimmer_color: str = "#ff69b4") -> Image.Image:
        """Generate RGBA mascot image.

        Args:
            direction: Eye direction (must be a key in ``Mascot._EYES``).
            active: Whether the mascot is in active/shimmer state.
            shimmer_color: Body color when ``active`` is True.

        Returns:
            A Pillow ``Image`` in RGBA mode with a transparent background.
        """
        width = Mascot.COLS * CELL_SIZE + PADDING * 2
        height = Mascot.ROWS * CELL_SIZE + PADDING * 2
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        body_color = shimmer_color if active else DEFAULT_BODY_COLOR
        self._draw_body(draw, body_color, active)
        self._draw_eyes(draw, direction)

        if active:
            # Subtle glow border
            glow_color = (*ImageColor.getrgb(shimmer_color), 80)
            draw.rectangle([0, 0, width - 1, height - 1], outline=glow_color, width=2)

        return img

    def _draw_body(self, draw: ImageDraw.Draw, color: str, active: bool) -> None:
        """Draw diamond body from ASCII template."""
        for row_idx, row_str in enumerate(Mascot._BODY):
            for col_idx, ch in enumerate(row_str):
                if ch == "█":
                    x0 = PADDING + col_idx * CELL_SIZE
                    y0 = PADDING + row_idx * CELL_SIZE
                    x1 = x0 + CELL_SIZE - 1
                    y1 = y0 + CELL_SIZE - 1
                    draw.rectangle([x0, y0, x1, y1], fill=color)

    def _draw_eyes(self, draw: ImageDraw.Draw, direction: str) -> None:
        """Draw eyes at position for given direction."""
        (left_row, left_col), (right_row, right_col) = Mascot._EYES[direction]
        for row, col in ((left_row, left_col), (right_row, right_col)):
            x0 = PADDING + col * CELL_SIZE
            y0 = PADDING + row * CELL_SIZE
            x1 = x0 + CELL_SIZE - 1
            y1 = y0 + CELL_SIZE - 1
            # White sclera
            draw.rectangle([x0, y0, x1, y1], fill="#ffffff")
            # Black pupil (centered small square)
            pupil_size = max(2, CELL_SIZE // 3)
            px0 = x0 + (CELL_SIZE - pupil_size) // 2
            py0 = y0 + (CELL_SIZE - pupil_size) // 2
            px1 = px0 + pupil_size - 1
            py1 = py0 + pupil_size - 1
            draw.rectangle([px0, py0, px1, py1], fill="#000000")
