"""Combine multiple single-resolution ICO files into one multi-resolution icon."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def combine_icons(source_dir: str, output_path: str) -> None:
    """Read *.ico files from source_dir and save as one multi-resolution ICO."""
    src = Path(source_dir)
    icons = sorted(src.glob("*.ico"))
    if not icons:
        raise FileNotFoundError(f"No .ico files found in {source_dir}")

    images: list[Image.Image] = []
    for path in icons:
        # ICO files may contain multiple sizes; load all sizes from each file.
        with Image.open(path) as img:
            for size in img.ico.sizes():
                img.seek(0)
                # Load the specific size
                ico_img = Image.open(path)
                ico_img.size = size
                images.append(ico_img.convert("RGBA"))

    if not images:
        raise ValueError("No icon images loaded")

    # Remove duplicates by size, keeping largest bit depth for each size.
    seen: dict[tuple[int, int], Image.Image] = {}
    for img in images:
        if img.size not in seen:
            seen[img.size] = img

    sorted_images = [seen[size] for size in sorted(seen.keys(), reverse=True)]
    sorted_images[0].save(
        output_path,
        format="ICO",
        sizes=[img.size for img in sorted_images],
        append_images=sorted_images[1:],
    )
    print(f"Saved multi-resolution icon: {output_path}")
    print(f"Sizes: {[img.size for img in sorted_images]}")


if __name__ == "__main__":
    combine_icons("E:/DDDESKKKK/ico", "E:/DDDESKKKK/holle_music/assets/icon.ico")
