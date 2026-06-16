"""MascotRenderer — renders the ASCII mascot as a transparent PNG using Pillow."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageColor

from holle_music.widgets import Mascot, _SHIMMER_PALETTES, _SHIMMER_INTERVAL, _current_palette


CELL_W: int = 10   # terminal char width
CELL_H: int = 20   # terminal char height (2x width for square aspect)
PADDING: int = 4
DEFAULT_BODY_COLOR: str = "#ffffff"
DARK_BODY_COLOR: str = "#000000"


class MascotRenderer:
    """Render the ASCII mascot as an RGBA PNG image."""

    def render(
        self,
        direction: str,
        active: bool,
        palette_name: str = "pink",
        shimmer_idx: int = 0,
        volume: float = 1.0,
        main_color: str = "light",
    ) -> Image.Image:
        """Generate RGBA mascot image.

        Args:
            direction: Eye direction (must be a key in ``Mascot._EYES``).
            active: Whether the mascot is in active/shimmer state.
            palette_name: Name of the shimmer palette theme.
            shimmer_idx: Index into the palette for the current color.
            volume: Current volume 0.0-1.0; controls how much of the body shimmers.

        Returns:
            A Pillow ``Image`` in RGBA mode with a transparent background.
        """
        width = Mascot.COLS * CELL_W + PADDING * 2
        height = Mascot.ROWS * CELL_H + PADDING * 2
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        body_base = DARK_BODY_COLOR if main_color == "dark" else DEFAULT_BODY_COLOR
        if active:
            palette = _SHIMMER_PALETTES.get(palette_name, _SHIMMER_PALETTES["pink"])
            body_color = palette[shimmer_idx % len(palette)]
        else:
            body_color = body_base

        self._draw_body(draw, body_color, active, volume, body_base)
        self._draw_eyes(draw, direction, main_color)

        return img

    @staticmethod
    def content_rect() -> tuple[int, int, int, int]:
        """Return the bounding box of the mascot's non-transparent content.

        The mascot image includes transparent padding around the diamond body.
        This rect (left, top, right, bottom) is relative to the image top-left
        and can be used to place UI elements flush against the actual graphics.
        """
        min_col = min((row_str.find("█") for row_str in Mascot._BODY if "█" in row_str), default=0)
        max_col = max((row_str.rfind("█") for row_str in Mascot._BODY if "█" in row_str), default=0)
        min_row = next((i for i, row in enumerate(Mascot._BODY) if "█" in row), 0)
        max_row = len(Mascot._BODY) - next((i for i, row in enumerate(reversed(Mascot._BODY)) if "█" in row), 0) - 1

        left = PADDING + min_col * CELL_W
        top = PADDING + min_row * CELL_H
        right = PADDING + (max_col + 1) * CELL_W
        bottom = PADDING + (max_row + 1) * CELL_H
        return left, top, right, bottom

    def _draw_body(
        self,
        draw: ImageDraw.Draw,
        color: str,
        active: bool,
        volume: float,
        body_base: str = DEFAULT_BODY_COLOR,
    ) -> None:
        """Draw diamond body from ASCII template.

        The shimmer is applied to the lower portion of the body based on volume:
        volume >= 0.5 -> whole body shimmers,
        volume 0.25 -> lower half shimmers,
        volume 0.0 -> no shimmer (all body_base color).
        """
        total_rows = len(Mascot._BODY)
        # Map volume so that 30% is full shimmer, below 30% scales linearly.
        scaled = min(1.0, volume / 0.3)
        # Determine the first row that should use the shimmer color.
        shimmer_start_row = int(total_rows * (1.0 - max(0.0, min(1.0, scaled))))

        for row_idx, row_str in enumerate(Mascot._BODY):
            if active and row_idx >= shimmer_start_row:
                body_color = color
            else:
                body_color = body_base
            for col_idx, ch in enumerate(row_str):
                if ch == "█":
                    x0 = PADDING + col_idx * CELL_W
                    y0 = PADDING + row_idx * CELL_H
                    x1 = x0 + CELL_W - 1
                    y1 = y0 + CELL_H - 1
                    draw.rectangle([x0, y0, x1, y1], fill=body_color)

    def _draw_eyes(self, draw: ImageDraw.Draw, direction: str, main_color: str = "light") -> None:
        """Draw eyes at position for given direction."""
        (left_row, left_col), (right_row, right_col) = Mascot._EYES[direction]
        eye_color = "#ffffff" if main_color == "dark" else "#000000"
        for row, col in ((left_row, left_col), (right_row, right_col)):
            x0 = PADDING + col * CELL_W
            y0 = PADDING + row * CELL_H
            x1 = x0 + CELL_W - 1
            y1 = y0 + CELL_H - 1
            # Solid eye (white on dark body, black on light body)
            draw.rectangle([x0, y0, x1, y1], fill=eye_color)
