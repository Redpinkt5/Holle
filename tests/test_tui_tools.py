"""Tests for holle_music.tui_tools."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from holle_music.models import Song
from holle_music.tui_tools import TUITools


@pytest.fixture
def app():
    app = MagicMock()
    app._original_songs = [
        Song(path="/tmp/1.mp3", title="浮夸", artist="陈奕迅"),
        Song(path="/tmp/2.mp3", title="十年", artist="陈奕迅"),
        Song(path="/tmp/3.mp3", title="晴天", artist="周杰伦"),
    ]
    app.player.playlist = app._original_songs
    return app


def test_execute_parses_json_string_arguments(app):
    tools = TUITools(app)
    result = tools.execute("search_local", '{"query": "陈奕迅"}')
    assert "浮夸" in result
    assert "十年" in result


def test_execute_accepts_dict_arguments(app):
    tools = TUITools(app)
    result = tools.execute("search_local", {"query": "周杰伦"})
    assert "晴天" in result


def test_execute_handles_empty_json_string(app):
    tools = TUITools(app)
    result = tools.execute("get_playlist", "")
    assert "播放列表" in result


def test_play_song_uses_last_search_results(app):
    tools = TUITools(app)
    tools.execute("search_local", '{"query": "陈奕迅"}')
    result = tools.execute("play_song", '{"title": "浮夸"}')
    assert "正在播放" in result
    app.player.play.assert_called_once()


def test_unknown_tool_returns_error(app):
    tools = TUITools(app)
    assert tools.execute("not_a_tool", "{}") == "未知工具: not_a_tool"
