from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from adapters.rss.rss_xml_gateway import RssXmlGateway
from domain.exceptions import RssFetchError

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_rss.xml"
SAMPLE_XML = FIXTURE_PATH.read_bytes()

DEFAULT_SOURCE_NAME = "ナルエビちゃんニュース"


def _mock_urlopen(content: bytes = SAMPLE_XML, status: int = 200):
    """contextmanager 互換の mock response を返すヘルパー."""
    response = MagicMock()
    response.read.return_value = content
    response.status = status
    response.getcode.return_value = status
    response.__enter__ = lambda self: response
    response.__exit__ = lambda self, *args: None
    return response


def _make_gateway(
    *,
    rss_url: str = "https://news.nullevi.app/rss",
    user_agent: str = "UA",
    source_name: str = DEFAULT_SOURCE_NAME,
    time_provider=None,
) -> RssXmlGateway:
    kwargs = {
        "rss_url": rss_url,
        "user_agent": user_agent,
        "source_name": source_name,
    }
    if time_provider is not None:
        kwargs["time_provider"] = time_provider
    return RssXmlGateway(**kwargs)


def test_sends_chrome_user_agent_header():
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["headers"] = dict(request.header_items())
        captured["url"] = request.full_url
        return _mock_urlopen()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        gw = _make_gateway(user_agent="Mozilla/5.0 Chrome/124.0 TestUA")
        gw.fetch_all()

    ua_value = None
    for key, val in captured["headers"].items():
        if key.lower() == "user-agent":
            ua_value = val
    assert ua_value is not None
    assert "Mozilla" in ua_value
    assert "Chrome" in ua_value
    assert captured["url"].startswith("https://news.nullevi.app/rss")
    assert "_=" in captured["url"]


def test_parses_cdata_titles():
    with patch("urllib.request.urlopen", return_value=_mock_urlopen()):
        gw = _make_gateway()
        items = gw.fetch_all()
    titles = [i.title for i in items]
    assert "グーグル、AIを悪用した大規模ハッキング未遂を初検知" in titles
    assert "危険すぎるAI「クロード・ミュトス」対策、週内にも作業部会" in titles


def test_parses_categories_as_csv_tuple():
    with patch("urllib.request.urlopen", return_value=_mock_urlopen()):
        gw = _make_gateway()
        items = gw.fetch_all()

    google_item = [i for i in items if "グーグル" in i.title][0]
    assert google_item.categories == (
        "Google",
        "AI悪用",
        "サイバーセキュリティ",
        "脆弱性",
    )


def test_handles_item_without_category():
    with patch("urllib.request.urlopen", return_value=_mock_urlopen()):
        gw = _make_gateway()
        items = gw.fetch_all()
    no_cat = [i for i in items if i.title == "カテゴリ無しエントリ"][0]
    assert no_cat.categories == ()


def test_parses_three_items_total():
    with patch("urllib.request.urlopen", return_value=_mock_urlopen()):
        gw = _make_gateway()
        items = gw.fetch_all()
    assert len(items) == 3


def test_propagates_source_name_to_items():
    with patch("urllib.request.urlopen", return_value=_mock_urlopen()):
        gw = _make_gateway(source_name="Wireless Wire News")
        items = gw.fetch_all()
    assert all(i.source_name == "Wireless Wire News" for i in items)


def test_http_error_raises_rss_fetch_error():
    import urllib.error

    def raising(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://news.nullevi.app/rss", 403, "Forbidden", {}, None
        )

    with patch("urllib.request.urlopen", side_effect=raising):
        gw = _make_gateway()
        with pytest.raises(RssFetchError) as excinfo:
            gw.fetch_all()
        assert excinfo.value.status_code == 403


def test_url_error_raises_rss_fetch_error():
    import urllib.error

    def raising(*args, **kwargs):
        raise urllib.error.URLError("connection refused")

    with patch("urllib.request.urlopen", side_effect=raising):
        gw = _make_gateway()
        with pytest.raises(RssFetchError) as excinfo:
            gw.fetch_all()
        assert excinfo.value.status_code is None


def test_malformed_xml_raises_rss_fetch_error():
    with patch(
        "urllib.request.urlopen", return_value=_mock_urlopen(content=b"<not-xml>")
    ):
        gw = _make_gateway()
        with pytest.raises(RssFetchError):
            gw.fetch_all()


# ----- Stage 1: cache-buster URL -----

def test_appends_cache_buster_query_when_no_existing_query():
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        return _mock_urlopen()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        gw = _make_gateway(time_provider=lambda: 1715750400.0)
        gw.fetch_all()

    assert captured["url"] == "https://news.nullevi.app/rss?_=1715750400"


def test_appends_cache_buster_with_ampersand_when_query_exists():
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        return _mock_urlopen()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        gw = _make_gateway(
            rss_url="https://news.nullevi.app/rss?foo=bar",
            time_provider=lambda: 1715750400.0,
        )
        gw.fetch_all()

    assert captured["url"] == "https://news.nullevi.app/rss?foo=bar&_=1715750400"


def test_cache_buster_changes_per_call():
    captured_urls = []

    def fake_urlopen(request, timeout=None):
        captured_urls.append(request.full_url)
        return _mock_urlopen()

    times = iter([1715750400.0, 1715750500.0])
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        gw = _make_gateway(time_provider=lambda: next(times))
        gw.fetch_all()
        gw.fetch_all()

    assert captured_urls[0] == "https://news.nullevi.app/rss?_=1715750400"
    assert captured_urls[1] == "https://news.nullevi.app/rss?_=1715750500"


# ----- Stage 2: no-cache HTTP headers -----

def _captured_headers_lower(request) -> dict[str, str]:
    return {key.lower(): val for key, val in request.header_items()}


def test_sends_cache_control_no_cache_header():
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["headers"] = _captured_headers_lower(request)
        return _mock_urlopen()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        gw = _make_gateway()
        gw.fetch_all()

    assert captured["headers"].get("cache-control") == "no-cache, no-store, max-age=0"


def test_sends_pragma_no_cache_header():
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["headers"] = _captured_headers_lower(request)
        return _mock_urlopen()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        gw = _make_gateway()
        gw.fetch_all()

    assert captured["headers"].get("pragma") == "no-cache"


def test_preserves_user_agent_and_accept_headers():
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["headers"] = _captured_headers_lower(request)
        return _mock_urlopen()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        gw = _make_gateway(user_agent="Mozilla/5.0 Chrome/124.0 TestUA")
        gw.fetch_all()

    assert "Mozilla" in captured["headers"].get("user-agent", "")
    assert "rss+xml" in captured["headers"].get("accept", "")


# ----- Stage 3: integration & error-path original-URL preservation -----

def test_http_error_still_carries_original_url_in_message():
    import urllib.error

    def raising(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://news.nullevi.app/rss", 403, "Forbidden", {}, None
        )

    with patch("urllib.request.urlopen", side_effect=raising):
        gw = _make_gateway(time_provider=lambda: 1715750400.0)
        with pytest.raises(RssFetchError) as excinfo:
            gw.fetch_all()

    assert "https://news.nullevi.app/rss" in str(excinfo.value)
    assert "?_=" not in str(excinfo.value)
    assert excinfo.value.final_url == "https://news.nullevi.app/rss?_=1715750400"


def test_integration_full_fetch_with_cache_busting():
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["headers"] = _captured_headers_lower(request)
        return _mock_urlopen()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        gw = _make_gateway(time_provider=lambda: 1715750400.0)
        items = gw.fetch_all()

    assert len(items) == 3
    assert captured["url"] == "https://news.nullevi.app/rss?_=1715750400"
    assert captured["headers"].get("cache-control") == "no-cache, no-store, max-age=0"
    assert captured["headers"].get("pragma") == "no-cache"


# ----- Stage 6: Multiple <category> element support -----

MULTI_CATEGORY_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "sample_multi_category.xml"
)
MULTI_CATEGORY_XML = MULTI_CATEGORY_FIXTURE_PATH.read_bytes()


def test_parses_multiple_category_elements_into_tuple():
    """Wireless Wire 型: 3 つの <category> 要素を持つ item が全カテゴリを保持する。"""
    with patch(
        "urllib.request.urlopen",
        return_value=_mock_urlopen(content=MULTI_CATEGORY_XML),
    ):
        gw = _make_gateway(
            rss_url="https://wirelesswire.jp/feed/",
            source_name="Wireless Wire News",
        )
        items = gw.fetch_all()

    target = [
        i for i in items if i.title == "科学技術芸術と社会の交差点"
    ][0]
    assert target.categories == (
        "科学技術芸術と社会",
        "働き方と人材",
        "考えるメディア",
    )


def test_preserves_single_csv_category_backward_compatibility():
    """ナルエビ型: 単一 <category> 内の CSV 文字列が引き続き正しく分割される。"""
    with patch("urllib.request.urlopen", return_value=_mock_urlopen()):
        gw = _make_gateway()
        items = gw.fetch_all()

    google_item = [i for i in items if "グーグル" in i.title][0]
    assert google_item.categories == (
        "Google",
        "AI悪用",
        "サイバーセキュリティ",
        "脆弱性",
    )


def test_handles_mixed_with_empty_category_elements():
    """空タグと有効タグが混在する item で、空要素は除外される。"""
    with patch(
        "urllib.request.urlopen",
        return_value=_mock_urlopen(content=MULTI_CATEGORY_XML),
    ):
        gw = _make_gateway(
            rss_url="https://wirelesswire.jp/feed/",
            source_name="Wireless Wire News",
        )
        items = gw.fetch_all()

    mixed = [i for i in items if i.title == "空 category 要素を含むエントリ"][0]
    assert mixed.categories == ("有効カテゴリ",)
