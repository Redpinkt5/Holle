"""Tests for holle_music.pet.ai_tools."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from holle_music.pet.ai_tools import AITools


@pytest.fixture
def player():
    player = MagicMock()
    player.get_state.return_value = {
        "playlist": [
            {"title": "浮夸", "artist": "陈奕迅", "path": "/tmp/1.mp3"},
            {"title": "十年", "artist": "陈奕迅", "path": "/tmp/2.mp3"},
            {"title": "晴天", "artist": "周杰伦", "path": "/tmp/3.mp3"},
        ],
        "song": None,
        "playing": False,
    }
    return player


def test_execute_parses_json_string_arguments(player):
    tools = AITools(player)
    result = tools.execute("search_local", '{"query": "陈奕迅"}')
    assert "浮夸" in result
    assert "十年" in result


def test_execute_accepts_dict_arguments(player):
    tools = AITools(player)
    result = tools.execute("search_local", {"query": "周杰伦"})
    assert "晴天" in result


def test_execute_handles_empty_json_string(player):
    tools = AITools(player)
    result = tools.execute("get_playlist", "")
    assert "播放列表" in result


def test_play_song_uses_last_search_results(player):
    tools = AITools(player)
    tools.execute("search_local", '{"query": "陈奕迅"}')
    result = tools.execute("play_song", '{"title": "浮夸"}')
    assert "正在播放" in result
    assert player._send_cmd.called


def test_unknown_tool_returns_error(player):
    tools = AITools(player)
    assert tools.execute("not_a_tool", "{}") == "未知工具: not_a_tool"
