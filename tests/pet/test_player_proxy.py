"""Tests for PetPlayer."""

import json
import time
from pathlib import Path

import pytest

from holle_music.pet.player_proxy import PetPlayer


class TestPetPlayer:
    def test_initial_state(self):
        player = PetPlayer()
        assert player.mode in ("sequential", "random", "repeat")
        assert player.is_playing is False

    def test_cycle_mode(self):
        player = PetPlayer()
        modes = []
        for _ in range(4):
            modes.append(player.mode)
            player.cycle_mode()
        assert modes[0] == "sequential"
        assert modes[1] == "random"
        assert modes[2] == "repeat"
        assert modes[3] == "sequential"

    def test_write_cmd(self, tmp_path, monkeypatch):
        pet_dir = tmp_path / ".holle_music"
        pet_dir.mkdir()
        state = {"playing": False, "time": int(time.time())}
        (pet_dir / "pet_state.json").write_text(
            json.dumps(state), encoding="utf-8"
        )
        monkeypatch.setattr(
            "holle_music.pet.player_proxy.PetPlayer._ipc_dir",
            property(lambda self: pet_dir),
        )
        player = PetPlayer()
        player.toggle_play()
        cmd_file = pet_dir / "pet_cmd.json"
        assert cmd_file.exists()
        data = json.loads(cmd_file.read_text(encoding="utf-8"))
        assert data["cmd"] == "toggle"
        assert isinstance(data["time"], (int, float))

    def test_read_state(self, tmp_path, monkeypatch):
        pet_dir = tmp_path / ".holle_music"
        pet_dir.mkdir()
        state = {
            "playing": True,
            "song": {"title": "Test Song", "artist": "Test Artist"},
            "mode": "random",
            "time": int(time.time()),
        }
        state_file = pet_dir / "pet_state.json"
        state_file.write_text(json.dumps(state), encoding="utf-8")
        monkeypatch.setattr(
            "holle_music.pet.player_proxy.PetPlayer._ipc_dir",
            property(lambda self: pet_dir),
        )
        player = PetPlayer()
        result = player.get_state()
        assert result["playing"] is True
        assert result["song"]["title"] == "Test Song"
        assert result["mode"] == "random"
