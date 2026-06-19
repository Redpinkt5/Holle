"""Tests for holle_music.settings persistence and migration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from holle_music import settings


@pytest.fixture
def clean_settings(monkeypatch, tmp_path):
    """Isolate settings files to a temporary directory for each test."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)

    package_dir = tmp_path / "package"
    package_dir.mkdir()
    monkeypatch.setattr(settings, "_old_settings_path", lambda: package_dir / ".holle_settings.json")
    monkeypatch.setattr(settings, "_legacy_color_path", lambda: package_dir / ".holle_color.json")

    # Ensure _settings_path picks up the mocked home
    yield


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_load_settings_returns_defaults_when_no_files_exist(clean_settings):
    result = settings.load_settings()
    assert result == settings.DEFAULT_SETTINGS


def test_load_settings_reads_from_new_path(clean_settings):
    new_path = settings._settings_path()
    custom = {"color": "blue", "volume": 0.5}
    _write_json(new_path, custom)

    result = settings.load_settings()
    assert result["color"] == "blue"
    assert result["volume"] == 0.5
    assert result["play_mode"] == settings.DEFAULT_SETTINGS["play_mode"]


def test_load_settings_migrates_old_settings_to_new_path(clean_settings):
    old_path = settings._old_settings_path()
    new_path = settings._settings_path()
    _write_json(old_path, {"color": "red", "volume": 0.3})

    assert not new_path.exists()
    result = settings.load_settings()

    assert new_path.exists()
    assert result["color"] == "red"
    assert result["volume"] == 0.3
    migrated = json.loads(new_path.read_text(encoding="utf-8"))
    assert migrated["color"] == "red"


def test_load_settings_prefers_new_path_over_old_path(clean_settings):
    """When both new and old paths exist, new path wins (migration is skipped)."""
    old_path = settings._old_settings_path()
    new_path = settings._settings_path()
    _write_json(old_path, {"color": "red", "volume": 0.3})
    _write_json(new_path, {"color": "green", "volume": 0.8})

    result = settings.load_settings()
    assert result["color"] == "green"
    assert result["volume"] == 0.8


def test_load_settings_falls_back_to_old_path_when_migration_skipped(clean_settings, monkeypatch):
    """When new path is absent and migration is skipped, old path is read directly."""
    def _noop_migrate():
        pass

    monkeypatch.setattr(settings, "_migrate_settings", _noop_migrate)
    old_path = settings._old_settings_path()
    _write_json(old_path, {"color": "cyan", "volume": 0.42})

    result = settings.load_settings()
    assert result["color"] == "cyan"
    assert result["volume"] == 0.42
    assert result["play_mode"] == settings.DEFAULT_SETTINGS["play_mode"]


def test_load_settings_falls_back_to_legacy_color_file(clean_settings):
    legacy_path = settings._legacy_color_path()
    _write_json(legacy_path, {"color": "purple"})

    result = settings.load_settings()
    assert result["color"] == "purple"
    assert result["volume"] == settings.DEFAULT_SETTINGS["volume"]


def test_set_setting_writes_only_to_new_path(clean_settings):
    settings.set_setting("color", "yellow")

    new_path = settings._settings_path()
    assert new_path.exists()
    data = json.loads(new_path.read_text(encoding="utf-8"))
    assert data["color"] == "yellow"

    old_path = settings._old_settings_path()
    assert not old_path.exists()


def test_save_settings_preserves_existing_keys(clean_settings):
    settings.set_setting("color", "orange")
    settings.set_setting("volume", 0.25)

    result = settings.load_settings()
    assert result["color"] == "orange"
    assert result["volume"] == 0.25
    assert result["play_mode"] == settings.DEFAULT_SETTINGS["play_mode"]


def test_load_settings_returns_defaults_on_corrupt_json(clean_settings):
    new_path = settings._settings_path()
    new_path.write_text("not valid json", encoding="utf-8")
    result = settings.load_settings()
    assert result == settings.DEFAULT_SETTINGS


def test_load_settings_returns_defaults_on_non_dict_json(clean_settings):
    new_path = settings._settings_path()
    _write_json(new_path, ["invalid"])
    result = settings.load_settings()
    assert result == settings.DEFAULT_SETTINGS
