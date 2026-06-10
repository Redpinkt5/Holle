import pytest
from holle_music.pet.click_zone import ClickZone


def test_center_click():
    zone = ClickZone()
    assert zone.detect(70, 70, 140, 140) == "center"


def test_left_click():
    zone = ClickZone()
    assert zone.detect(10, 70, 140, 140) == "left"


def test_right_click():
    zone = ClickZone()
    assert zone.detect(130, 70, 140, 140) == "right"


def test_top_click():
    zone = ClickZone()
    assert zone.detect(70, 10, 140, 140) == "top"


def test_bottom_click():
    zone = ClickZone()
    assert zone.detect(70, 130, 140, 140) == "bottom"


def test_outside_returns_empty():
    zone = ClickZone()
    assert zone.detect(0, 0, 140, 140) == ""
