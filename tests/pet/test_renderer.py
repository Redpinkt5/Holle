"""Tests for MascotRenderer."""

import os
import tempfile

import pytest
from PIL import Image

from holle_music.pet.renderer import MascotRenderer


class TestMascotRenderer:
    def test_render_returns_image(self):
        renderer = MascotRenderer()
        img = renderer.render("center", active=False)
        assert isinstance(img, Image.Image)
        assert img.mode == "RGBA"
        assert img.width > 0
        assert img.height > 0

    def test_render_different_directions(self):
        renderer = MascotRenderer()
        directions = [
            "center",
            "up",
            "down",
            "left",
            "right",
            "top_left",
            "top_right",
            "bottom_left",
            "bottom_right",
        ]
        for direction in directions:
            img = renderer.render(direction, active=False)
            assert isinstance(img, Image.Image)
            assert img.mode == "RGBA"

    def test_render_active_changes_appearance(self):
        renderer = MascotRenderer()
        inactive = renderer.render("center", active=False)
        active = renderer.render("center", active=True, shimmer_color="#00ff00")
        # Compare pixel data; active should differ from inactive
        assert inactive.tobytes() != active.tobytes()

    def test_save_to_file(self):
        renderer = MascotRenderer()
        img = renderer.render("center", active=False)
        tmpdir = tempfile.mkdtemp()
        try:
            path = os.path.join(tmpdir, "mascot.png")
            img.save(path)
            assert os.path.exists(path)
            loaded = Image.open(path)
            assert loaded.mode == "RGBA"
            loaded.close()
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
