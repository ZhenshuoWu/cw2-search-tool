"""JSON persistence for built search indexes and crawl reports."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from src.crawler import CrawlFailure, CrawlRequest
from src.indexer import InvertedIndex, PageMetadata, WordStats

DEFAULT_INDEX_PATH = Path("data/index.json")
DEFAULT_REPORT_PATH = Path("data/crawl_report.json")
INDEX_VERSION = 1


def save_index(index: InvertedIndex, path: Path | str = DEFAULT_INDEX_PATH) -> Path:
    """Save an inverted index as deterministic UTF-8 JSON."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(index_to_dict(index), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def load_index(path: Path | str = DEFAULT_INDEX_PATH) -> InvertedIndex:
    """Load an inverted index previously written by save_index."""

    input_path = Path(path)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    return index_from_dict(data)


def index_to_dict(index: InvertedIndex) -> dict[str, Any]:
    """Convert an InvertedIndex into plain JSON-compatible objects."""

    return {
        "version": INDEX_VERSION,
        "pages": {
            url: {
                "url": metadata.url,
                "title": metadata.title,
                "word_count": metadata.word_count,
                "searchable_text": metadata.searchable_text,
                "quote_count": metadata.quote_count,
            }
            for url, metadata in sorted(index.pages.items())
        },
        "words": {
            word: {
                url: {
                    "frequency": stats.frequency,
                    "positions": list(stats.positions),
                }
                for url, stats in sorted(page_entries.items())
            }
            for word, page_entries in sorted(index.words.items())
        },
    }


def index_from_dict(data: dict[str, Any]) -> InvertedIndex:
    """Reconstruct an InvertedIndex from JSON-compatible objects."""

    pages = {
        url: PageMetadata(
            url=str(metadata.get("url", url)),
            title=str(metadata.get("title", "")),
            word_count=int(metadata.get("word_count", 0)),
            searchable_text=str(metadata.get("searchable_text", "")),
            quote_count=int(metadata.get("quote_count", 0)),
        )
        for url, metadata in data.get("pages", {}).items()
    }
    words = {
        word: {
            url: WordStats(
                frequency=int(stats.get("frequency", 0)),
                positions=[int(position) for position in stats.get("positions", [])],
            )
            for url, stats in page_entries.items()
        }
        for word, page_entries in data.get("words", {}).items()
    }
    return InvertedIndex(words=words, pages=pages)


def save_crawl_report(
    *,
    path: Path | str = DEFAULT_REPORT_PATH,
    pages_crawled: int,
    politeness_delay: float,
    requests: list[CrawlRequest],
    errors: list[CrawlFailure],
) -> Path:
    """Save a crawl audit report for demonstration and debugging."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "pages_crawled": pages_crawled,
        "politeness_delay_seconds": politeness_delay,
        "requests": [asdict(request) for request in requests],
        "errors": [asdict(error) for error in errors],
    }
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path
