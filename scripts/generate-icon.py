"""Generate a simple Holle Music icon from the diamond mascot shape."""

from __future__ import annotations

from PIL import Image, ImageDraw


def _draw_diamond(img_size: int, color: tuple[int, int, int]) -> Image.Image:
    """Draw a filled diamond on a transparent background."""
    img = Image.new("RGBA", (img_size, img_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = img_size // 2
    cy = img_size // 2
    # Diamond polygon: top, right, bottom, left
    inset = int(img_size * 0.18)
    polygon = [
        (cx, inset),
        (img_size - inset, cy),
        (cx, img_size - inset),
        (inset, cy),
    ]
    draw.polygon(polygon, fill=color)
    return img


def generate_icon(output_path: str) -> None:
    """Generate a multi-resolution .ico file."""
    color = (255, 105, 180)  # pink
    sizes = [256, 128, 64, 48, 32, 16]
    images = [_draw_diamond(size, color) for size in sizes]
    images[0].save(output_path, format="ICO", sizes=[(s, s) for s in sizes], append_images=images[1:])


if __name__ == "__main__":
    generate_icon("assets/icon.ico")
    print("Generated assets/icon.ico")
