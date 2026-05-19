"""Small search helpers for the current in-memory index."""

from __future__ import annotations

from src.indexer import (
    InvertedIndex,
    PageDocument,
    WordStats,
    lookup_word,
    tokenize,
)


def demo_pages() -> list[PageDocument]:
    """Return a tiny local dataset for exercising the current index structure."""

    return [
        PageDocument(
            url="demo://page-1",
            html="""
            <html>
              <head><title>Demo Quotes One</title></head>
              <body>
                <div class="quote">
                  <span class="text">Good friends are good company.</span>
                  <small class="author">Demo Author</small>
                  <div class="tags">
                    <a class="tag">friendship</a>
                    <a class="tag">good</a>
                  </div>
                </div>
              </body>
            </html>
            """,
        ),
        PageDocument(
            url="demo://page-2",
            html="""
            <html>
              <head><title>Demo Quotes Two</title></head>
              <body>
                <div class="quote">
                  <span class="text">Indifference is the opposite of care.</span>
                  <small class="author">Demo Writer</small>
                  <div class="tags">
                    <a class="tag">reflection</a>
                  </div>
                </div>
              </body>
            </html>
            """,
        ),
    ]


def find_pages(index: InvertedIndex, query: str) -> list[str]:
    """Return pages containing all query tokens, sorted by frequency then URL."""

    tokens = tokenize(query)
    if not tokens:
        return []

    page_sets = [set(index.words.get(token, {})) for token in tokens]
    if not page_sets:
        return []

    matches = set.intersection(*page_sets)
    return sorted(
        matches,
        key=lambda url: (-sum(index.words[token][url].frequency for token in tokens), url),
    )


def format_word_entry(index: InvertedIndex, word: str) -> str:
    """Return a readable representation of one inverted-index word entry."""

    entries = lookup_word(index, word)
    tokens = tokenize(word)
    label = tokens[0] if len(tokens) == 1 else word.strip()

    if not entries:
        return f"No index entry for '{label}'."

    lines = [f"Index entry for '{label}':"]
    for url, stats in sorted(entries.items()):
        lines.append(_format_stats(url, stats))
    return "\n".join(lines)


def format_find_results(index: InvertedIndex, query: str) -> str:
    """Return readable search results for a single- or multi-word query."""

    urls = find_pages(index, query)
    tokens = tokenize(query)
    if not tokens:
        return "Usage: find <query terms>"
    if not urls:
        return f"No pages found for: {' '.join(tokens)}"

    lines = [f"Pages matching {' '.join(tokens)}:"]
    lines.extend(urls)
    return "\n".join(lines)


def format_index_summary(index: InvertedIndex) -> str:
    """Return a compact summary of the current in-memory index."""

    return f"Index ready: {len(index.pages)} pages, {len(index.words)} unique words."


def _format_stats(url: str, stats: WordStats) -> str:
    return f"- {url}: frequency={stats.frequency}, positions={stats.positions}"
