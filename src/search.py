"""Search helpers for ranked lookup over the inverted index."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches
import math
import re

from src.indexer import (
    InvertedIndex,
    PageDocument,
    WordStats,
    lookup_word,
    tokenize,
)

PHRASE_PATTERN = re.compile(r'"([^"]+)"')
HIGHLIGHT_TEMPLATE = "[{}]"


@dataclass(frozen=True)
class SearchResult:
    """One ranked page result for a query."""

    url: str
    score: float
    snippet: str
    matched_tokens: tuple[str, ...]
    positions: tuple[tuple[str, tuple[int, ...]], ...]


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
    """Return matching page URLs ordered by ranked search score."""

    return [result.url for result in ranked_search(index, query)]


def ranked_search(
    index: InvertedIndex,
    query: str,
    *,
    limit: int | None = None,
) -> list[SearchResult]:
    """Return pages containing all query tokens, ranked with BM25 scoring."""

    tokens = tokenize(query)
    if not tokens:
        return []

    unique_tokens = tuple(dict.fromkeys(tokens))
    page_sets = [set(index.words.get(token, {})) for token in unique_tokens]
    if not page_sets:
        return []

    matches = set.intersection(*page_sets)
    phrases = _extract_phrase_tokens(query)
    if phrases:
        matches = {
            url
            for url in matches
            if all(_page_contains_phrase(index, url, phrase) for phrase in phrases)
        }

    results = [
        SearchResult(
            url=url,
            score=_bm25_score(index, url, unique_tokens),
            snippet=make_snippet(index, url, unique_tokens),
            matched_tokens=unique_tokens,
            positions=tuple(
                (token, tuple(index.words[token][url].positions))
                for token in unique_tokens
            ),
        )
        for url in matches
    ]
    results.sort(key=lambda result: (-result.score, result.url))
    if limit is not None:
        return results[:limit]
    return results


def suggest_terms(
    index: InvertedIndex,
    query: str,
    *,
    max_suggestions: int = 3,
    cutoff: float = 0.74,
) -> dict[str, tuple[str, ...]]:
    """Suggest close vocabulary terms for query tokens missing from the index."""

    vocabulary = sorted(index.words)
    suggestions: dict[str, tuple[str, ...]] = {}
    for token in dict.fromkeys(tokenize(query)):
        if token in index.words:
            continue
        matches = get_close_matches(token, vocabulary, n=max_suggestions, cutoff=cutoff)
        if matches:
            suggestions[token] = tuple(matches)
    return suggestions


def make_snippet(index: InvertedIndex, url: str, tokens: tuple[str, ...]) -> str:
    """Return a compact highlighted text excerpt for a matching page."""

    metadata = index.pages.get(url)
    text = " ".join((metadata.searchable_text if metadata else url).split())
    if not text:
        text = metadata.title if metadata and metadata.title else url

    start = _first_match_offset(text, tokens)
    width = 160
    if start is None:
        excerpt = text[:width]
        prefix = ""
    else:
        excerpt_start = max(0, start - 45)
        excerpt = text[excerpt_start : excerpt_start + width]
        prefix = "... " if excerpt_start > 0 else ""

    suffix = " ..." if len(excerpt) < len(text) and not text.endswith(excerpt) else ""
    return prefix + highlight_terms(excerpt.strip(), tokens) + suffix


def highlight_terms(text: str, tokens: tuple[str, ...]) -> str:
    """Mark exact token matches in a display string with square brackets."""

    terms = sorted({token for token in tokens if token}, key=len, reverse=True)
    if not terms:
        return text
    pattern = re.compile(
        r"(?i)(?<![a-z0-9])("
        + "|".join(re.escape(term) for term in terms)
        + r")(?![a-z0-9])"
    )
    return pattern.sub(lambda match: HIGHLIGHT_TEMPLATE.format(match.group(0)), text)


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

    tokens = tokenize(query)
    if not tokens:
        return "Usage: find <query terms>"

    results = ranked_search(index, query)
    if not results:
        lines = [f"No pages found for: {' '.join(tokens)}"]
        suggestion_line = _format_suggestions(suggest_terms(index, query))
        if suggestion_line:
            lines.append(suggestion_line)
        return "\n".join(lines)

    lines = [f"Pages matching {' '.join(tokens)} (ranked by BM25):"]
    for number, result in enumerate(results, start=1):
        lines.append(f"{number}. {result.url}")
        lines.append(
            f"   score={result.score:.3f} matched={', '.join(result.matched_tokens)}"
        )
        if result.snippet:
            lines.append(f"   snippet: {result.snippet}")
    return "\n".join(lines)


def format_index_summary(index: InvertedIndex) -> str:
    """Return a compact summary of the current in-memory index."""

    return f"Index ready: {len(index.pages)} pages, {len(index.words)} unique words."


def _format_stats(url: str, stats: WordStats) -> str:
    return f"- {url}: frequency={stats.frequency}, positions={stats.positions}"


def _bm25_score(index: InvertedIndex, url: str, tokens: tuple[str, ...]) -> float:
    document_count = max(len(index.pages), 1)
    average_length = _average_document_length(index)
    document_length = max(
        index.pages.get(url).word_count if url in index.pages else 0,
        1,
    )
    k1 = 1.5
    b = 0.75
    score = 0.0

    for token in tokens:
        page_entries = index.words.get(token, {})
        stats = page_entries.get(url)
        if stats is None:
            continue
        document_frequency = len(page_entries)
        idf = math.log(
            1
            + (document_count - document_frequency + 0.5)
            / (document_frequency + 0.5)
        )
        tf = stats.frequency
        denominator = tf + k1 * (1 - b + b * (document_length / average_length))
        score += idf * ((tf * (k1 + 1)) / denominator)

    return score


def _average_document_length(index: InvertedIndex) -> float:
    if not index.pages:
        return 1.0
    total = sum(metadata.word_count for metadata in index.pages.values())
    return max(total / len(index.pages), 1.0)


def _extract_phrase_tokens(query: str) -> list[tuple[str, ...]]:
    phrases: list[tuple[str, ...]] = []
    for match in PHRASE_PATTERN.finditer(query):
        tokens = tuple(tokenize(match.group(1)))
        if len(tokens) > 1:
            phrases.append(tokens)
    return phrases


def _page_contains_phrase(
    index: InvertedIndex,
    url: str,
    phrase_tokens: tuple[str, ...],
) -> bool:
    first_positions = index.words.get(phrase_tokens[0], {}).get(url)
    if first_positions is None:
        return False

    remaining_position_sets = [
        set(index.words.get(token, {}).get(url, WordStats()).positions)
        for token in phrase_tokens[1:]
    ]
    for start in first_positions.positions:
        if all(
            start + offset in positions
            for offset, positions in enumerate(remaining_position_sets, start=1)
        ):
            return True
    return False


def _first_match_offset(text: str, tokens: tuple[str, ...]) -> int | None:
    offsets: list[int] = []
    for token in tokens:
        match = re.search(
            r"(?i)(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])",
            text,
        )
        if match:
            offsets.append(match.start())
    if not offsets:
        return None
    return min(offsets)


def _format_suggestions(suggestions: dict[str, tuple[str, ...]]) -> str:
    if not suggestions:
        return ""
    if len(suggestions) == 1:
        matches = next(iter(suggestions.values()))
        return f"Did you mean: {', '.join(matches)}?"
    parts = [
        f"{token} -> {', '.join(matches)}"
        for token, matches in suggestions.items()
    ]
    return "Suggestions: " + "; ".join(parts)
