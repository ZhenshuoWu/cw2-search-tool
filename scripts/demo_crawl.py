"""Run the crawler and quote parser as a small standalone demonstration."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from textwrap import shorten
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.crawler import DEFAULT_START_URL, WebsiteCrawler
from src.indexer import extract_quotes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crawl quotes.toscrape.com pages and print parsed quote data."
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=2,
        help="Maximum number of pages to crawl. Defaults to 2 for a quick demo.",
    )
    parser.add_argument(
        "--start-url",
        default=DEFAULT_START_URL,
        help="Starting URL for the crawl.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    crawler = WebsiteCrawler(start_url=args.start_url, max_pages=args.pages)

    started_at = perf_counter()
    pages = crawler.crawl()
    elapsed = perf_counter() - started_at

    print(f"Crawled pages: {len(pages)}")
    print(f"Elapsed seconds: {elapsed:.2f}")
    print(f"Errors: {len(crawler.errors)}")

    for page_number, page in enumerate(pages, start=1):
        quotes = extract_quotes(page.html)
        print()
        print(f"Page {page_number}: {page.url}")
        print(f"Status: {page.status_code}")
        print(f"Quotes parsed: {len(quotes)}")

        for quote_number, quote in enumerate(quotes[:3], start=1):
            print(f"  {quote_number}. {shorten(quote.text, width=100, placeholder='...')}")
            print(f"     Author: {quote.author or '(missing)'}")
            print(f"     Tags: {', '.join(quote.tags) if quote.tags else '(none)'}")

    if crawler.errors:
        print()
        print("Errors:")
        for error in crawler.errors:
            print(f"- {error.url}: {error.reason}")


if __name__ == "__main__":
    main()
