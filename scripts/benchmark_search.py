"""Benchmark indexing and ranked search on deterministic synthetic quote pages."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import statistics
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.indexer import InvertedIndex, PageDocument, build_inverted_index
from src.search import ranked_search


DEFAULT_QUERIES = (
    "good friends",
    '"good friends"',
    "indifference",
    "wisdom life",
    "missingterm",
)

QUOTE_TEMPLATES = (
    (
        "Good friends, good books, and a sleepy conscience: this is the ideal life.",
        "Mark Twain",
        ("friends", "books", "life"),
    ),
    (
        "Indifference and neglect often do much more damage than outright dislike.",
        "J.K. Rowling",
        ("indifference", "choices"),
    ),
    (
        "The world as we have created it is a process of our thinking.",
        "Albert Einstein",
        ("world", "thinking", "change"),
    ),
    (
        "It is not that I am so smart. But I stay with the questions much longer.",
        "Albert Einstein",
        ("questions", "wisdom"),
    ),
    (
        "Life is what happens to us while we are making other plans.",
        "Allen Saunders",
        ("life", "planning"),
    ),
    (
        "A friend is someone who knows all about you and still loves you.",
        "Elbert Hubbard",
        ("friendship", "love"),
    ),
)


@dataclass(frozen=True)
class BenchmarkResult:
    """Summary metrics from a benchmark run."""

    pages: int
    repeat: int
    total_tokens: int
    unique_words: int
    build_median_ms: float
    query_median_ms: dict[str, float]
    query_result_counts: dict[str, int]


def make_synthetic_pages(page_count: int, *, quotes_per_page: int = 4) -> list[PageDocument]:
    """Create deterministic quote-like pages without network access."""

    pages: list[PageDocument] = []
    for page_number in range(1, page_count + 1):
        quote_blocks = []
        for offset in range(quotes_per_page):
            text, author, tags = QUOTE_TEMPLATES[(page_number + offset) % len(QUOTE_TEMPLATES)]
            tag_links = "".join(f'<a class="tag">{tag}</a>' for tag in tags)
            quote_blocks.append(
                f"""
                <div class="quote">
                  <span class="text">{text}</span>
                  <small class="author">{author}</small>
                  <div class="tags">{tag_links}</div>
                </div>
                """
            )

        pages.append(
            PageDocument(
                url=f"benchmark://page/{page_number}/",
                html=f"""
                <html>
                  <head><title>Benchmark Page {page_number}</title></head>
                  <body>{''.join(quote_blocks)}</body>
                </html>
                """,
            )
        )
    return pages


def run_benchmark(
    *,
    page_count: int,
    repeat: int,
    queries: tuple[str, ...] = DEFAULT_QUERIES,
) -> BenchmarkResult:
    """Measure index construction and ranked queries."""

    pages = make_synthetic_pages(page_count)
    build_times: list[float] = []
    index = InvertedIndex()

    for _ in range(repeat):
        started_at = perf_counter()
        index = build_inverted_index(pages)
        build_times.append(_elapsed_ms(started_at))

    query_times: dict[str, list[float]] = {query: [] for query in queries}
    query_result_counts: dict[str, int] = {}
    for query in queries:
        results = []
        for _ in range(repeat):
            started_at = perf_counter()
            results = ranked_search(index, query)
            query_times[query].append(_elapsed_ms(started_at))
        query_result_counts[query] = len(results)

    return BenchmarkResult(
        pages=page_count,
        repeat=repeat,
        total_tokens=sum(metadata.word_count for metadata in index.pages.values()),
        unique_words=len(index.words),
        build_median_ms=statistics.median(build_times),
        query_median_ms={
            query: statistics.median(times)
            for query, times in query_times.items()
        },
        query_result_counts=query_result_counts,
    )


def format_result(result: BenchmarkResult) -> str:
    """Return a human-readable benchmark report."""

    lines = [
        "CW2 Search Benchmark",
        f"Pages: {result.pages}",
        f"Repeat count: {result.repeat}",
        f"Total tokens indexed: {result.total_tokens}",
        f"Unique words: {result.unique_words}",
        f"Median build time: {result.build_median_ms:.3f} ms",
        "Median ranked query times:",
    ]
    for query, median_ms in result.query_median_ms.items():
        count = result.query_result_counts[query]
        lines.append(f"- {query}: {median_ms:.3f} ms ({count} results)")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark CW2 inverted-index build and ranked search."
    )
    parser.add_argument("--pages", type=int, default=500)
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument(
        "--query",
        action="append",
        default=None,
        help="Query to benchmark. Can be passed more than once.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.pages < 1:
        raise SystemExit("--pages must be at least 1")
    if args.repeat < 1:
        raise SystemExit("--repeat must be at least 1")

    queries = tuple(args.query) if args.query else DEFAULT_QUERIES
    print(format_result(run_benchmark(page_count=args.pages, repeat=args.repeat, queries=queries)))


def _elapsed_ms(started_at: float) -> float:
    return (perf_counter() - started_at) * 1000


if __name__ == "__main__":
    main()
