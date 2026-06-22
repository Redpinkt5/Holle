import sys
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

    # Make Bilibili API return empty so we fall through to DDGS
    fake_bilibili_response = b'{"code": 0, "data": {"result": []}}'
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

    # Mock _search_urls_bilibili to return empty (fall through to DDGS)
    with patch.object(searcher, "_search_urls_bilibili", return_value=[]):
        with patch("holle_music.bilibili_searcher.DDGS") as MockDDGS:
            MockDDGS.return_value.__enter__.return_value.text.side_effect = fake_ddgs
            with patch.object(searcher, "_song_from_url") as mock_song:
                mock_song.side_effect = [
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
    searcher = BilibiliSearcher()

    def fake_ddgs(text, max_results):
        return []

    # Mock _search_urls_bilibili to return empty, DDGS also empty
    with patch.object(searcher, "_search_urls_bilibili", return_value=[]):
        with patch("holle_music.bilibili_searcher.DDGS") as MockDDGS:
            MockDDGS.return_value.__enter__.return_value.text.side_effect = fake_ddgs
            results = searcher.search("xxxxxxxxxxxx")

    assert results == []


def test_song_from_url_skips_invalid():
    searcher = BilibiliSearcher()
    # Non-Bilibili URL should return None (bvid extraction fails)
    import sys
    mock_yt_dlp = MagicMock()
    with patch.dict(sys.modules, {"yt_dlp": mock_yt_dlp}):
        assert searcher._song_from_url("https://example.com") is None
