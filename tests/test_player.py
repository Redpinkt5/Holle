"""Tests for audio player engine."""

import pytest
from holle_music.player import Player, PlayerState
from holle_music.models import Song
from pathlib import Path


class TestPlayerState:
    def test_initial_state_is_stopped(self):
        player = Player()
        assert player.state == PlayerState.STOPPED

    def test_state_transitions(self):
        assert PlayerState.STOPPED != PlayerState.PLAYING
        assert PlayerState.PLAYING != PlayerState.PAUSED
        assert len(PlayerState) == 3


class TestPlayer:
    def test_player_initialization(self):
        player = Player()
        assert player.volume == 1.0
        assert player.current_song is None
        assert not player.is_playing

    def test_set_volume_clamps_range(self):
        player = Player()
        player.set_volume(0.5)
        assert player.volume == 0.5
        player.set_volume(2.0)
        assert player.volume == 1.0
        player.set_volume(-0.5)
        assert player.volume == 0.0

    def test_load_playlist(self):
        player = Player()
        songs = [
            Song(path=Path(f"/music/{i}.mp3"))
            for i in range(3)
        ]
        player.load_playlist(songs)
        assert len(player.playlist) == 3
        assert player.current_index == 0
        assert player.current_song == songs[0]

    def test_load_empty_playlist_does_nothing(self):
        player = Player()
        res = player.load_playlist([])
        assert res is True
        assert player.current_song is None

    def test_next_previous(self):
        player = Player()
        songs = [
            Song(path=Path(f"/music/{i}.mp3"))
            for i in range(3)
        ]
        player.load_playlist(songs)
        assert player.current_index == 0

        player.next()
        assert player.current_index == 1

        player.next()
        assert player.current_index == 2

        player.next()
        assert player.current_index == 0  # wraps around

        player.previous()
        assert player.current_index == 2

    def test_previous_on_single_song(self):
        player = Player()
        songs = [Song(path=Path("/music/a.mp3"))]
        player.load_playlist(songs)
        player.previous()
        assert player.current_index == 0
