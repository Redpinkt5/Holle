from pathlib import Path
from unittest.mock import MagicMock, patch

from holle_music.bilibili_searcher import BilibiliSearcher, _extract_bvid
from holle_music.models import Song


def test_extract_bvid_from_url():
    assert _extract_bvid("https://www.bilibili.com/video/BV1xx411c7mD") == "BV1xx411c7mD"
    assert _extract_bvid("https://b23.tv/BV1xx411c7mD") == "BV1xx411c7mD"
    assert _extract_bvid("https://example.com") is None


def make_ddgs_result(href):
    return {"href": href}


def make_ydl_info(title, uploader="UP主", duration=180, thumbnails=None):
    return {
        "title": title,
        "uploader": uploader,
        "duration": duration,
        "thumbnails": thumbnails or [{"url": "https://cover.jpg"}],
    }


def test_search_parses_entries():
    searcher = BilibiliSearcher()

    ddgs_results = [
        make_ddgs_result("https://www.bilibili.com/video/BV1xx411c7mD"),
        make_ddgs_result("https://www.bilibili.com/video/BV1yy411c7mD"),
    ]

    def fake_ddgs(text, max_results):
        return ddgs_results

    mock_ydl = MagicMock()
    mock_ydl.extract_info.side_effect = [
        make_ydl_info("晴天"),
        make_ydl_info("七里香"),
    ]

    with patch("holle_music.bilibili_searcher.DDGS") as MockDDGS:
        MockDDGS.return_value.__enter__.return_value.text.side_effect = fake_ddgs
        with patch("holle_music.bilibili_searcher.yt_dlp") as mock_ydl_mod:
            mock_ydl_mod.YoutubeDL.return_value.__enter__.return_value = mock_ydl
            results = searcher.search("周杰伦", max_results=2)

    assert len(results) == 2
    assert results[0].bvid == "BV1xx411c7mD"
    assert results[0].title == "晴天 (web)"
    assert results[0].source == "bilibili"


def test_search_returns_empty_on_no_results():
    searcher = BilibiliSearcher()

    def fake_ddgs(text, max_results):
        return []

    with patch("holle_music.bilibili_searcher.DDGS") as MockDDGS:
        MockDDGS.return_value.__enter__.return_value.text.side_effect = fake_ddgs
        results = searcher.search("xxxxxxxxxxxx")

    assert results == []


def test_song_from_url_skips_invalid():
    searcher = BilibiliSearcher()
    assert searcher._song_from_url("https://example.com") is None
