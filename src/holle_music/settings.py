"""Persistent user settings for Holle Music.

Settings are stored next to this module in ``.holle_settings.json``.
For backward compatibility, the legacy ``.holle_color.json`` file is still
read for color if the new settings file does not exist.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS: dict[str, Any] = {
    "color": "pink",
    "volume": 1.0,
    "music_dir": "E:/Music",
    "play_mode": "sequential",
    "main_color": "light",
    "current_song_path": "",
    "current_song_title": "",
}


def _settings_path() -> Path:
    """Return path to the unified settings file."""
    return Path(__file__).parent / ".holle_settings.json"


def _legacy_color_path() -> Path:
    """Return path to the legacy color-only config file."""
    return Path(__file__).parent / ".holle_color.json"


def load_settings() -> dict[str, Any]:
    """Load user settings from disk.

    Tries the unified ``.holle_settings.json`` first. If that is missing,
    falls back to the legacy ``.holle_color.json`` for the color value.
    Returns ``DEFAULT_SETTINGS`` when neither file exists or reading fails.
    """
    path = _settings_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged = dict(DEFAULT_SETTINGS)
                merged.update(data)
                return merged
        except Exception:
            pass

    legacy = _legacy_color_path()
    if legacy.exists():
        try:
            data = json.loads(legacy.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged = dict(DEFAULT_SETTINGS)
                merged["color"] = data.get("color", DEFAULT_SETTINGS["color"])
                return merged
        except Exception:
            pass

    return dict(DEFAULT_SETTINGS)


def save_settings(updates: dict[str, Any]) -> None:
    """Merge ``updates`` into the current settings and persist to disk.

    Write failures are silently ignored so the app keeps working even when
    the install directory is not writable.
    """
    settings = load_settings()
    settings.update(updates)
    path = _settings_path()
    try:
        path.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def get_setting(key: str, default: Any = None) -> Any:
    """Return a single setting value, or ``default`` if missing."""
    return load_settings().get(key, default)


def set_setting(key: str, value: Any) -> None:
    """Set a single setting and persist it."""
    save_settings({key: value})
