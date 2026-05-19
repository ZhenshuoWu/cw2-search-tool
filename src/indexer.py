"""HTML content extraction for quote pages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from bs4 import BeautifulSoup, Tag


@dataclass(frozen=True)
class QuoteRecord:
    """Searchable content from one quote block."""

    text: str
    author: str
    tags: tuple[str, ...]


def extract_quotes(html: str) -> list[QuoteRecord]:
    """Return quote text, author names, and tags from a quote listing page."""

    soup = BeautifulSoup(html or "", "html.parser")
    quotes: list[QuoteRecord] = []

    for quote_node in soup.select("div.quote"):
        if not isinstance(quote_node, Tag):
            continue

        text = _text_from_first(quote_node, ".text")
        author = _text_from_first(quote_node, ".author")
        tags = tuple(
            tag_text
            for tag_text in (_clean_text(tag) for tag in quote_node.select(".tags .tag"))
            if tag_text
        )

        if text or author or tags:
            quotes.append(QuoteRecord(text=text, author=author, tags=tags))

    return quotes


def extract_searchable_text(html: str) -> str:
    """Return a single text string containing every searchable quote field."""

    parts: list[str] = []
    for quote in extract_quotes(html):
        parts.extend(_present([quote.text, quote.author, *quote.tags]))
    return " ".join(parts)


def _text_from_first(container: Tag, selector: str) -> str:
    node = container.select_one(selector)
    if node is None:
        return ""
    return _clean_text(node)


def _clean_text(node: Tag) -> str:
    return " ".join(node.get_text(" ", strip=True).split())


def _present(values: Iterable[str]) -> list[str]:
    return [value for value in values if value]
