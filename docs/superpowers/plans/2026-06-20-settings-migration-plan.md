# v0.3.0 Settings Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Holle Music's persistent settings from the Python package directory (`src/holle_music/.holle_settings.json`) to the user's home directory (`~/.holle_music/settings.json`), with automatic migration of existing settings and full backward compatibility.

**Architecture:** Keep the public API of `settings.py` unchanged (`load_settings`, `save_settings`, `set_setting`, `get_setting`). Internally, redirect the storage path to `~/.holle_music/settings.json` and add a one-time migration helper that copies legacy settings from the old package-local path. All other modules continue calling `settings.py` without modification.

**Tech Stack:** Python 3.10+, `pathlib`, `json`, `pytest`

---

## File Structure

| File | Responsibility |
|---|---|
| `src/holle_music/settings.py` | Defines settings path, loading, saving, and migration logic. The only production file to change. |
| `tests/test_settings.py` | Unit tests for migration, read priority, save behavior, legacy fallback, and defaults. |

---

## Task 1: Update `src/holle_music/settings.py`

**Files:**
- Modify: `src/holle_music/settings.py`

- [ ] **Step 1: Change `_settings_path()` to use the user home directory**

Replace the existing `_settings_path()` function with:

```python
def _settings_path() -> Path:
    """Return path to the unified settings file in the user's home directory."""
    settings_dir = Path.home() / ".holle_music"
    try:
        settings_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return settings_dir / "settings.json"
```

- [ ] **Step 2: Add legacy path helper**

Add the following function right after `_settings_path()`:

```python
def _old_settings_path() -> Path:
    """Return the legacy settings file next to this module (pre-0.3.0)."""
    return Path(__file__).parent / ".holle_settings.json"
```

- [ ] **Step 3: Add migration helper**

Add the following function right after `_old_settings_path()`:

```python
def _migrate_settings() -> None:
    """Copy settings from the legacy package location to the user home if needed.

    This is a one-time migration for users upgrading from versions before 0.3.0.
    The old file is left in place as a backup.
    """
    new_path = _settings_path()
    if new_path.exists():
        return

    old_path = _old_settings_path()
    if not old_path.exists():
        return

    try:
        data = json.loads(old_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            new_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except Exception:
        pass
```

- [ ] **Step 4: Hook migration into `load_settings()`**

At the very beginning of `load_settings()`, before any other logic, add:

```python
    _migrate_settings()
```

The full `load_settings()` should now start like this:

```python
def load_settings() -> dict[str, Any]:
    """Load user settings from disk."""
    _migrate_settings()
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
        ...
```

- [ ] **Step 5: Keep legacy fallback for old `.holle_color.json`**

Ensure the existing legacy `.holle_color.json` fallback remains after the new-path check. Do not remove it.

- [ ] **Step 6: Update `save_settings()` to write only to the new path**

Ensure `save_settings()` uses `_settings_path()` (it already does via `path = _settings_path()`). No code change is required unless the existing implementation used a different path.

---

## Task 2: Write Tests in `tests/test_settings.py`

**Files:**
- Create: `tests/test_settings.py`

- [ ] **Step 1: Create the test file with imports and fixtures**

Create `tests/test_settings.py` with:

```python
"""Tests for holle_music.settings persistence and migration."""

from __future__ import annotations

import json
from pathlib import Path

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


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 2: Add default settings test**

```python
def test_load_settings_returns_defaults_when_no_files_exist(clean_settings):
    result = settings.load_settings()
    assert result == settings.DEFAULT_SETTINGS
```

- [ ] **Step 3: Add new-path read test**

```python
def test_load_settings_reads_from_new_path(clean_settings):
    new_path = settings._settings_path()
    custom = {"color": "blue", "volume": 0.5}
    _write_json(new_path, custom)

    result = settings.load_settings()
    assert result["color"] == "blue"
    assert result["volume"] == 0.5
    assert result["play_mode"] == settings.DEFAULT_SETTINGS["play_mode"]
```

- [ ] **Step 4: Add migration test**

```python
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
```

- [ ] **Step 5: Add new-path priority test**

```python
def test_load_settings_prefers_new_path_over_old_path(clean_settings):
    old_path = settings._old_settings_path()
    new_path = settings._settings_path()
    _write_json(old_path, {"color": "red", "volume": 0.3})
    _write_json(new_path, {"color": "green", "volume": 0.8})

    result = settings.load_settings()
    assert result["color"] == "green"
    assert result["volume"] == 0.8
```

- [ ] **Step 6: Add legacy `.holle_color.json` fallback test**

```python
def test_load_settings_falls_back_to_legacy_color_file(clean_settings):
    legacy_path = settings._legacy_color_path()
    _write_json(legacy_path, {"color": "purple"})

    result = settings.load_settings()
    assert result["color"] == "purple"
    assert result["volume"] == settings.DEFAULT_SETTINGS["volume"]
```

- [ ] **Step 7: Add save-to-new-path test**

```python
def test_set_setting_writes_only_to_new_path(clean_settings):
    settings.set_setting("color", "yellow")

    new_path = settings._settings_path()
    assert new_path.exists()
    data = json.loads(new_path.read_text(encoding="utf-8"))
    assert data["color"] == "yellow"

    old_path = settings._old_settings_path()
    assert not old_path.exists()
```

- [ ] **Step 8: Add save-does-not-lose-existing-settings test**

```python
def test_save_settings_preserves_existing_keys(clean_settings):
    settings.set_setting("color", "orange")
    settings.set_setting("volume", 0.25)

    result = settings.load_settings()
    assert result["color"] == "orange"
    assert result["volume"] == 0.25
    assert result["play_mode"] == settings.DEFAULT_SETTINGS["play_mode"]
```

---

## Task 3: Run Tests

**Files:**
- Test: `tests/test_settings.py`

- [ ] **Step 1: Run the new tests**

Run:

```bash
PYTHONPATH=src python -m pytest tests/test_settings.py -v
```

Expected: all tests pass.

- [ ] **Step 2: Run the full test suite**

Run:

```bash
PYTHONPATH=src python -m pytest tests/ -v
```

Expected: all tests pass (existing tests should not be affected).

---

## Task 4: Manual Verification

**Files:**
- Verify runtime behavior: `src/holle_music/settings.py`

- [ ] **Step 1: Verify settings are written to the new location**

Run:

```bash
PYTHONPATH=src python -c "from holle_music.settings import set_setting, load_settings; set_setting('color', 'pink'); print(load_settings()['color'])"
```

Then check that `~/.holle_music/settings.json` exists and contains `"color": "pink"`.

- [ ] **Step 2: Verify migration from old location**

If an old `src/holle_music/.holle_settings.json` exists with custom values, delete `~/.holle_music/settings.json` and run:

```bash
PYTHONPATH=src python -c "from holle_music.settings import load_settings; print(load_settings())"
```

Confirm that `~/.holle_music/settings.json` is created with the old values.

---

## Task 5: Commit

**Files:**
- `src/holle_music/settings.py`
- `tests/test_settings.py`

- [ ] **Step 1: Stage changes**

```bash
git add src/holle_music/settings.py tests/test_settings.py
```

- [ ] **Step 2: Commit**

```bash
git commit -m "feat(settings): persist user settings in ~/.holle_music/settings.json

- Move settings path from package directory to user home directory.
- Add automatic one-time migration from legacy .holle_settings.json.
- Keep fallback to legacy .holle_color.json for color.
- Add tests for migration, read priority, save behavior, and defaults.

Fixes config loss in pip installs and PyInstaller onefile executables."
```

---

## Self-Review Checklist

- [ ] **Spec coverage:** Every section of the design spec is covered: new path, migration, read priority, legacy fallback, save behavior, error handling.
- [ ] **No placeholders:** All steps contain exact code/commands; no TBD or "implement later".
- [ ] **Type consistency:** `load_settings`, `save_settings`, `set_setting`, `get_setting` signatures remain unchanged.
- [ ] **DRY:** Migration logic is isolated in `_migrate_settings()`.
- [ ] **YAGNI:** No additional features (e.g., migration marker file, `%APPDATA%` support) are included.
- [ ] **Test coverage:** Migration, new-path read, priority, legacy fallback, save behavior, and defaults are tested.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-20-settings-migration-plan.md`.

**Execution options:**

1. **Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - Execute tasks in this session using `executing-plans`, batch execution with checkpoints.

Which approach would you like?
