"""Tests for Bilibili search and audio download."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from holle_music.bilibili_searcher import BilibiliSearcher, _extract_bvid
from holle_music.models import Song


def test_extract_bvid_from_url():
    assert _extract_bvid("https://www.bilibili.com/video/BV1xx411c7mD") == "BV1xx411c7mD"
    assert _extract_bvid("https://b23.tv/BV1xx411c7mD") == "BV1xx411c7mD"
    assert _extract_bvid("https://example.com") is None


def test_search_parses_entries():
    """search() falls back to DDGS when Bilibili API returns empty, resolving URLs to Song objects."""
    searcher = BilibiliSearcher()

    # Mock _search_songs_from_api (Bilibili API) to return empty so we fall through
    # Mock _search_urls (DDGS fallback) to return a list of Song objects on ONE call
    with patch.object(searcher, "_search_songs_from_api", return_value=[]):
        with patch.object(searcher, "_search_urls") as mock_search_urls:
            mock_search_urls.return_value = [
                Song(
                    path=Path(""),
                    title="晴天 (web)",
                    artist="UP主",
                    duration=180.0,
                    source="bilibili",
                    bvid="BV1xx411c7mD",
                    web_url="https://www.bilibili.com/video/BV1xx411c7mD",
                    cover_url="https://cover.jpg",
                ),
                Song(
                    path=Path(""),
                    title="七里香 (web)",
                    artist="UP主",
                    duration=180.0,
                    source="bilibili",
                    bvid="BV1yy411c7mD",
                    web_url="https://www.bilibili.com/video/BV1yy411c7mD",
                    cover_url="https://cover.jpg",
                ),
            ]
            results = searcher.search("周杰伦", max_results=2)

    assert len(results) == 2
    assert results[0].bvid == "BV1xx411c7mD"
    assert results[0].title == "晴天 (web)"
    assert results[0].source == "bilibili"


def test_search_returns_empty_on_no_results():
    """search() returns empty when both Bilibili API and DDGS find nothing."""
    searcher = BilibiliSearcher()

    def fake_ddgs(text, max_results):
        return []

    # Make Bilibili API and DDGS both return empty
    with patch.object(searcher, "_search_songs_from_api", return_value=[]):
        with patch("holle_music.bilibili_searcher.DDGS") as MockDDGS:
            MockDDGS.return_value.__enter__.return_value.text.side_effect = fake_ddgs
            results = searcher.search("xxxxxxxxxxxx")

    assert results == []


def test_song_from_url_skips_invalid():
    """_song_from_url returns None for non-Bilibili URLs."""
    searcher = BilibiliSearcher()
    assert searcher._song_from_url("https://example.com") is None


def make_ddgs_result(href):
    return {"href": href}


def make_ydl_info(title, uploader="UP主", duration=180, thumbnails=None):
    return {
        "title": title,
        "uploader": uploader,
        "duration": duration,
        "thumbnails": thumbnails or [{"url": "https://cover.jpg"}],
    }
