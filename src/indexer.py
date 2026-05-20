"""HTML content extraction and inverted index construction for quote pages."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Iterable

from bs4 import BeautifulSoup, Tag

TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?")


@dataclass(frozen=True)
class QuoteRecord:
    """Searchable content from one quote block."""

    text: str
    author: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class PageDocument:
    """HTML content for one crawled page."""

    url: str
    html: str


@dataclass(frozen=True)
class PageMetadata:
    """Summary information stored alongside the inverted index."""

    url: str
    title: str
    word_count: int
    searchable_text: str = ""
    quote_count: int = 0


@dataclass
class WordStats:
    """Statistics for a word within a single page."""

    frequency: int = 0
    positions: list[int] = field(default_factory=list)


@dataclass
class InvertedIndex:
    """Mapping from normalized words to page-level occurrence statistics."""

    words: dict[str, dict[str, WordStats]] = field(default_factory=dict)
    pages: dict[str, PageMetadata] = field(default_factory=dict)


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


def tokenize(text: str) -> list[str]:
    """Return lowercase searchable tokens from free text."""

    return TOKEN_PATTERN.findall((text or "").lower())


def build_inverted_index(pages: Iterable[PageDocument]) -> InvertedIndex:
    """Build an inverted index from crawled page HTML documents."""

    index = InvertedIndex()

    for page in pages:
        quotes = extract_quotes(page.html)
        searchable_text = extract_searchable_text(page.html)
        tokens = tokenize(searchable_text)
        index.pages[page.url] = PageMetadata(
            url=page.url,
            title=extract_title(page.html),
            word_count=len(tokens),
            searchable_text=searchable_text,
            quote_count=len(quotes),
        )

        for position, token in enumerate(tokens):
            page_entries = index.words.setdefault(token, {})
            stats = page_entries.setdefault(page.url, WordStats())
            stats.frequency += 1
            stats.positions.append(position)

    return index


def lookup_word(index: InvertedIndex, word: str) -> dict[str, WordStats]:
    """Return page statistics for a normalized word, or an empty mapping."""

    tokens = tokenize(word)
    if len(tokens) != 1:
        return {}
    return index.words.get(tokens[0], {})


def extract_title(html: str) -> str:
    """Return the page title when present."""

    soup = BeautifulSoup(html or "", "html.parser")
    title = soup.select_one("title")
    if title is None:
        return ""
    return _clean_text(title)


def _text_from_first(container: Tag, selector: str) -> str:
    node = container.select_one(selector)
    if node is None:
        return ""
    return _clean_text(node)


def _clean_text(node: Tag) -> str:
    return " ".join(node.get_text(" ", strip=True).split())


def _present(values: Iterable[str]) -> list[str]:
    return [value for value in values if value]
