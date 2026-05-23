"""Tests for command parser."""

import pytest
from pathlib import Path
from holle_music.app import parse_command, Command, CommandType


class TestCommandParser:
    def test_play_command(self):
        cmd = parse_command("play 晴天")
        assert cmd.type == CommandType.PLAY
        assert cmd.args == "晴天"

    def test_pause_command(self):
        cmd = parse_command("pause")
        assert cmd.type == CommandType.PAUSE

    def test_resume_command(self):
        cmd = parse_command("resume")
        assert cmd.type == CommandType.PLAY

    def test_stop_command(self):
        cmd = parse_command("stop")
        assert cmd.type == CommandType.STOP

    def test_next_command(self):
        cmd = parse_command("next")
        assert cmd.type == CommandType.NEXT

    def test_prev_command(self):
        cmd = parse_command("prev")
        assert cmd.type == CommandType.PREVIOUS

    def test_volume_command(self):
        cmd = parse_command("volume 80")
        assert cmd.type == CommandType.VOLUME
        assert cmd.args == "80"

    def test_scan_command(self):
        cmd = parse_command("scan /music/rock")
        assert cmd.type == CommandType.SCAN
        assert cmd.args == "/music/rock"

    def test_playlist_command(self):
        cmd = parse_command("playlist 我的歌单")
        assert cmd.type == CommandType.PLAYLIST
        assert cmd.args == "我的歌单"

    def test_help_command(self):
        cmd = parse_command("help")
        assert cmd.type == CommandType.HELP

    def test_quit_command(self):
        cmd = parse_command("quit")
        assert cmd.type == CommandType.QUIT

    def test_empty_input(self):
        cmd = parse_command("")
        assert cmd.type == CommandType.NONE

    def test_unknown_command(self):
        cmd = parse_command("foobar")
        assert cmd.type == CommandType.UNKNOWN

    def test_trim_whitespace(self):
        cmd = parse_command("  play   晴天  ")
        assert cmd.type == CommandType.PLAY
        assert cmd.args == "晴天"
