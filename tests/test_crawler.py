from __future__ import annotations

from dataclasses import dataclass

import pytest
import requests

from src.crawler import (
    DEFAULT_POLITENESS_DELAY,
    WebsiteCrawler,
    extract_next_url,
    is_allowed_url,
    normalize_url,
)


@dataclass
class FakeResponse:
    url: str
    text: str
    status_code: int = 200


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, timeout):
        self.calls.append((url, timeout))
        response = self.responses[url]
        if isinstance(response, Exception):
            raise response
        return response


def quote_page(next_href=None):
    next_html = ""
    if next_href is not None:
        next_html = f'<li class="next"><a href="{next_href}">Next</a></li>'
    return f"""
    <html>
      <body>
        <div class="quote"><span class="text">A quote</span></div>
        <ul class="pager">{next_html}</ul>
      </body>
    </html>
    """


def test_crawler_follows_quote_pagination_links():
    start_url = "https://quotes.toscrape.com/"
    page_two_url = "https://quotes.toscrape.com/page/2/"
    session = FakeSession(
        {
            start_url: FakeResponse(start_url, quote_page("/page/2/")),
            page_two_url: FakeResponse(page_two_url, quote_page()),
        }
    )
    sleep_calls = []
    crawler = WebsiteCrawler(
        session=session,
        sleep_func=sleep_calls.append,
        time_func=lambda: 100.0,
    )

    pages = crawler.crawl()

    assert [page.url for page in pages] == [start_url, page_two_url]
    assert [call[0] for call in session.calls] == [start_url, page_two_url]
    assert crawler.errors == []
    assert [request.accepted for request in crawler.requests] == [True, True]
    assert [request.delay_seconds for request in crawler.requests] == [
        0.0,
        DEFAULT_POLITENESS_DELAY,
    ]


def test_crawler_waits_at_least_six_seconds_between_successive_requests():
    start_url = "https://quotes.toscrape.com/"
    page_two_url = "https://quotes.toscrape.com/page/2/"
    session = FakeSession(
        {
            start_url: FakeResponse(start_url, quote_page("/page/2/")),
            page_two_url: FakeResponse(page_two_url, quote_page()),
        }
    )
    sleep_calls = []
    crawler = WebsiteCrawler(
        session=session,
        sleep_func=sleep_calls.append,
        time_func=lambda: 0.0,
    )

    crawler.crawl()

    assert sleep_calls == [DEFAULT_POLITENESS_DELAY]


def test_crawler_only_waits_for_remaining_politeness_window():
    start_url = "https://quotes.toscrape.com/"
    page_two_url = "https://quotes.toscrape.com/page/2/"
    session = FakeSession(
        {
            start_url: FakeResponse(start_url, quote_page("/page/2/")),
            page_two_url: FakeResponse(page_two_url, quote_page()),
        }
    )
    times = iter([10.0, 12.5, 12.5])
    sleep_calls = []
    crawler = WebsiteCrawler(
        session=session,
        sleep_func=sleep_calls.append,
        time_func=lambda: next(times),
    )

    crawler.crawl()

    assert sleep_calls == [3.5]


def test_crawler_does_not_follow_external_next_links():
    start_url = "https://quotes.toscrape.com/"
    session = FakeSession(
        {
            start_url: FakeResponse(
                start_url,
                quote_page("https://example.com/page/2/"),
            ),
        }
    )
    crawler = WebsiteCrawler(session=session, sleep_func=lambda _: None)

    pages = crawler.crawl()

    assert [page.url for page in pages] == [start_url]
    assert len(session.calls) == 1


def test_crawler_records_request_errors_without_saving_page():
    start_url = "https://quotes.toscrape.com/"
    session = FakeSession(
        {
            start_url: requests.Timeout("timed out"),
        }
    )
    crawler = WebsiteCrawler(session=session, sleep_func=lambda _: None)

    pages = crawler.crawl()

    assert pages == []
    assert len(crawler.errors) == 1
    assert "request failed" in crawler.errors[0].reason


def test_crawler_records_non_success_status_without_saving_page():
    start_url = "https://quotes.toscrape.com/"
    session = FakeSession(
        {
            start_url: FakeResponse(start_url, "not found", status_code=404),
        }
    )
    crawler = WebsiteCrawler(session=session, sleep_func=lambda _: None)

    pages = crawler.crawl()

    assert pages == []
    assert len(crawler.errors) == 1
    assert "404" in crawler.errors[0].reason


def test_extract_next_url_returns_normalized_internal_url():
    next_url = extract_next_url(quote_page("/page/2/#top"), "https://quotes.toscrape.com/")

    assert next_url == "https://quotes.toscrape.com/page/2/"


def test_extract_next_url_returns_none_when_missing_or_external():
    assert extract_next_url("", "https://quotes.toscrape.com/") is None
    assert extract_next_url("<html><body>", "https://quotes.toscrape.com/") is None
    assert extract_next_url(quote_page(), "https://quotes.toscrape.com/") is None
    assert (
        extract_next_url(
            quote_page("https://example.com/page/2/"),
            "https://quotes.toscrape.com/",
        )
        is None
    )


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://quotes.toscrape.com/#top", "https://quotes.toscrape.com/"),
        ("HTTPS://QUOTES.TOSCRAPE.COM/page/2/", "https://quotes.toscrape.com/page/2/"),
    ],
)
def test_normalize_url_removes_fragments_and_lowercases_host(url, expected):
    assert normalize_url(url) == expected


def test_is_allowed_url_rejects_external_domains():
    assert is_allowed_url("https://quotes.toscrape.com/page/2/")
    assert not is_allowed_url("https://example.com/page/2/")
