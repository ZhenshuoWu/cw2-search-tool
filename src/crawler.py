"""Polite crawler for the quotes.toscrape.com listing pages."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from typing import Callable, Optional, Protocol
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup


DEFAULT_START_URL = "https://quotes.toscrape.com/"
DEFAULT_ALLOWED_DOMAIN = "quotes.toscrape.com"
DEFAULT_POLITENESS_DELAY = 6.0
DEFAULT_TIMEOUT = 10.0


class HttpSession(Protocol):
    """Small protocol for objects that can perform HTTP GET requests."""

    def get(self, url: str, timeout: float) -> requests.Response:
        """Return an HTTP response for the requested URL."""


@dataclass(frozen=True)
class CrawledPage:
    """HTML captured from a successfully crawled page."""

    url: str
    html: str
    status_code: int


@dataclass(frozen=True)
class CrawlFailure:
    """A page that could not be fetched or accepted."""

    url: str
    reason: str

def normalize_url(url: str) -> str:
    """Return a stable URL without fragments."""

    clean_url, _fragment = urldefrag(url)
    parsed = urlparse(clean_url)
    path = parsed.path or "/"
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            parsed.query,
            "",
        )
    )


def is_allowed_url(url: str, allowed_domain: str = DEFAULT_ALLOWED_DOMAIN) -> bool:
    """Return True when the URL belongs to the configured site."""

    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == allowed_domain


def extract_next_url(
    html: str,
    current_url: str,
    allowed_domain: str = DEFAULT_ALLOWED_DOMAIN,
) -> Optional[str]:
    """Find the next pagination URL from a quote listing page."""

    soup = BeautifulSoup(html, "html.parser")
    next_link = soup.select_one("li.next a[href]")
    if next_link is None:
        return None

    href = next_link.get("href")
    if not href:
        return None

    candidate = normalize_url(urljoin(current_url, href))
    if not is_allowed_url(candidate, allowed_domain):
        return None
    return candidate


class WebsiteCrawler:
    """Crawl quote listing pages while respecting a politeness delay."""

    def __init__(
        self,
        start_url: str = DEFAULT_START_URL,
        *,
        allowed_domain: str = DEFAULT_ALLOWED_DOMAIN,
        politeness_delay: float = DEFAULT_POLITENESS_DELAY,
        timeout: float = DEFAULT_TIMEOUT,
        session: Optional[HttpSession] = None,
        sleep_func: Callable[[float], None] = time.sleep,
        time_func: Callable[[], float] = time.monotonic,
        logger: Optional[logging.Logger] = None,
        max_pages: Optional[int] = None,
    ) -> None:
        self.start_url = normalize_url(start_url)
        self.allowed_domain = allowed_domain
        self.politeness_delay = politeness_delay
        self.timeout = timeout
        self.session = session or requests.Session()
        self.sleep_func = sleep_func
        self.time_func = time_func
        self.logger = logger or logging.getLogger(__name__)
        self.max_pages = max_pages
        self.errors: list[CrawlFailure] = []
        self._last_request_started_at: Optional[float] = None

    def crawl(self) -> list[CrawledPage]:
        """Crawl the quote pagination chain from the configured start page."""

        pages: list[CrawledPage] = []
        seen: set[str] = set()
        next_url: Optional[str] = self.start_url

        while next_url and next_url not in seen:
            if self.max_pages is not None and len(pages) >= self.max_pages:
                break

            seen.add(next_url)
            page = self.fetch_page(next_url)
            if page is None:
                break

            pages.append(page)
            next_url = extract_next_url(page.html, page.url, self.allowed_domain)

        return pages

    def fetch_page(self, url: str) -> Optional[CrawledPage]:
        """Fetch one allowed page and return None when it cannot be used."""

        normalized_url = normalize_url(url)
        if not is_allowed_url(normalized_url, self.allowed_domain):
            self._record_error(normalized_url, "URL is outside the allowed domain")
            return None

        self._respect_politeness()
        self._last_request_started_at = self.time_func()

        try:
            response = self.session.get(normalized_url, timeout=self.timeout)
        except requests.RequestException as exc:
            self._record_error(normalized_url, f"request failed: {exc}")
            return None

        status_code = getattr(response, "status_code", None)
        if status_code != 200:
            self._record_error(normalized_url, f"unexpected status code: {status_code}")
            return None

        final_url = normalize_url(getattr(response, "url", normalized_url) or normalized_url)
        if not is_allowed_url(final_url, self.allowed_domain):
            self._record_error(final_url, "response URL is outside the allowed domain")
            return None

        return CrawledPage(
            url=final_url,
            html=getattr(response, "text", ""),
            status_code=status_code,
        )

    def _respect_politeness(self) -> None:
        if self._last_request_started_at is None:
            return

        elapsed = self.time_func() - self._last_request_started_at
        remaining = self.politeness_delay - elapsed
        if remaining > 0:
            self.sleep_func(remaining)

    def _record_error(self, url: str, reason: str) -> None:
        self.errors.append(CrawlFailure(url=url, reason=reason))
        self.logger.warning("Skipping %s: %s", url, reason)
