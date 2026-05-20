"""Web visualization for the demo indexing data flow."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from src.indexer import (
    InvertedIndex,
    PageDocument,
    WordStats,
    build_inverted_index,
    extract_quotes,
    extract_searchable_text,
    extract_title,
    tokenize,
)
from src.search import demo_pages, find_pages, ranked_search
from src.storage import load_index

DEFAULT_QUERY = "good friends"
DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = {"en", "zh"}
TEXT = {
    "en": {
        "html_lang": "en",
        "title": "CW2 Trace Visualizer",
        "eyebrow": "CW2 Search Tool",
        "h1": "Trace Visualizer",
        "lede": "Follow the demo HTML through extraction, tokenization, index updates, and query intersection.",
        "pages": "Pages",
        "words": "Words",
        "query": "Query",
        "data_pipeline": "Data Pipeline",
        "pipeline_steps": ["HTML", "Quote records", "Searchable text", "Tokens", "Inverted index"],
        "query_trace": "Query trace",
        "language": "Language",
        "english": "English",
        "chinese": "中文",
        "update": "Update",
        "extraction": "Extraction And Tokenization",
        "demo_html": "Demo HTML",
        "quote_records": "Quote records",
        "author": "Author",
        "tags": "Tags",
        "missing": "(missing)",
        "missing_text": "(missing text)",
        "none": "(none)",
        "no_title": "No title",
        "empty": "(empty)",
        "tokens_with_positions": "Tokens with positions",
        "build_trace": "Build Trace",
        "build_note": "Each token updates: word -> page URL -> frequency and positions.",
        "page": "Page",
        "position": "Position",
        "token": "Token",
        "word_entry": "Word entry",
        "page_stats": "Page stats",
        "frequency": "Frequency",
        "positions": "Positions",
        "inverted_index": "Inverted Index",
        "query_intersection": "Query Intersection",
        "no_valid_tokens": "No valid tokens were found in the query.",
        "saved_index_note": "Rendering a saved index. Extraction and build traces are shown when demo pages are used.",
        "normalized_query": "Normalized query",
        "final_result": "Final result",
        "no_matches": "(no matches)",
    },
    "zh": {
        "html_lang": "zh-CN",
        "title": "CW2 数据流可视化",
        "eyebrow": "CW2 搜索工具",
        "h1": "数据流可视化",
        "lede": "观察 demo HTML 如何经过内容抽取、分词、索引更新，并最终完成查询集合交集。",
        "pages": "页面数",
        "words": "词条数",
        "query": "查询",
        "data_pipeline": "数据管线",
        "pipeline_steps": ["HTML", "Quote 记录", "可搜索文本", "Tokens", "倒排索引"],
        "query_trace": "查询追踪",
        "language": "语言",
        "english": "English",
        "chinese": "中文",
        "update": "更新",
        "extraction": "抽取与分词",
        "demo_html": "Demo HTML",
        "quote_records": "Quote 记录",
        "author": "作者",
        "tags": "标签",
        "missing": "（缺失）",
        "missing_text": "（缺少文本）",
        "none": "（无）",
        "no_title": "无标题",
        "empty": "（空）",
        "tokens_with_positions": "带位置的 Tokens",
        "build_trace": "构建追踪",
        "build_note": "每个 token 都会更新这个结构：word -> page URL -> frequency 和 positions。",
        "page": "页面",
        "position": "位置",
        "token": "Token",
        "word_entry": "词条",
        "page_stats": "页面统计",
        "frequency": "词频",
        "positions": "位置列表",
        "inverted_index": "倒排索引",
        "query_intersection": "查询集合交集",
        "no_valid_tokens": "查询中没有可用 token。",
        "saved_index_note": "当前展示的是已保存索引。使用 demo pages 时会显示抽取和构建追踪。",
        "normalized_query": "归一化查询",
        "final_result": "最终结果",
        "no_matches": "（无匹配）",
    },
}


@dataclass(frozen=True)
class BuildEvent:
    """One token update during index construction."""

    page_url: str
    position: int
    token: str
    word_action: str
    page_action: str
    before_frequency: int
    after_frequency: int
    positions: tuple[int, ...]


def render_trace_page(
    query: str = DEFAULT_QUERY,
    lang: str = DEFAULT_LANGUAGE,
    *,
    index: InvertedIndex | None = None,
    pages: list[PageDocument] | None = None,
) -> str:
    """Return a complete HTML page for visualizing the demo data flow."""

    lang = normalize_language(lang)
    text = TEXT[lang]
    trace_pages = demo_pages() if pages is None and index is None else pages or []
    index = index or build_inverted_index(trace_pages)
    query_tokens = tokenize(query)
    matching_pages = find_pages(index, query)
    build_events = collect_build_events(trace_pages)

    trace_sections = []
    if trace_pages:
        trace_sections.extend(
            [
                _page_flow(trace_pages, text),
                _build_flow(build_events, text),
            ]
        )
    else:
        trace_sections.append(_saved_index_note(text))

    return "\n".join(
        [
            "<!doctype html>",
            f'<html lang="{text["html_lang"]}">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{escape(text['title'])}</title>",
            f"<style>{_css()}</style>",
            "</head>",
            "<body>",
            '<main class="shell">',
            _header(query, index, text),
            _pipeline(text),
            _query_form(query, lang, text),
            *trace_sections,
            _index_view(index, text),
            _query_view(index, query, query_tokens, matching_pages, text),
            "</main>",
            "</body>",
            "</html>",
        ]
    )


def normalize_language(lang: str) -> str:
    """Return a supported language code."""

    return lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def collect_build_events(pages: list[PageDocument]) -> list[BuildEvent]:
    """Return step-by-step index mutations for visualization."""

    index = InvertedIndex()
    events: list[BuildEvent] = []

    for page in pages:
        tokens = tokenize(extract_searchable_text(page.html))
        for position, token in enumerate(tokens):
            word_created = token not in index.words
            page_entries = index.words.setdefault(token, {})
            page_created = page.url not in page_entries
            stats = page_entries.setdefault(page.url, WordStats())
            before_frequency = stats.frequency
            stats.frequency += 1
            stats.positions.append(position)
            events.append(
                BuildEvent(
                    page_url=page.url,
                    position=position,
                    token=token,
                    word_action="create" if word_created else "reuse",
                    page_action="create" if page_created else "reuse",
                    before_frequency=before_frequency,
                    after_frequency=stats.frequency,
                    positions=tuple(stats.positions),
                )
            )

    return events


class TraceRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler that serves the trace visualizer."""

    trace_index: InvertedIndex | None = None
    trace_pages: list[PageDocument] | None = None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in {"/", "/trace"}:
            self.send_error(404, "Not found")
            return

        params = parse_qs(parsed.query)
        query = params.get("q", [DEFAULT_QUERY])[0]
        lang = normalize_language(params.get("lang", [DEFAULT_LANGUAGE])[0])
        body = render_trace_page(
            query,
            lang,
            index=self.trace_index,
            pages=self.trace_pages,
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        """Keep the demo server quiet during tests and local use."""


def main() -> None:
    """Run the local trace web server."""

    parser = argparse.ArgumentParser(description="Run the CW2 trace visualizer.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--index",
        default="",
        help="Optional saved index JSON path, for example data/index.json.",
    )
    args = parser.parse_args()

    if args.index:
        TraceRequestHandler.trace_index = load_index(Path(args.index))
        TraceRequestHandler.trace_pages = []

    server = ThreadingHTTPServer((args.host, args.port), TraceRequestHandler)
    print(f"Trace visualizer running at http://{args.host}:{args.port}/")
    server.serve_forever()


def _header(query: str, index: InvertedIndex, text: dict[str, object]) -> str:
    return f"""
    <header class="top">
      <div>
        <p class="eyebrow">{escape(str(text['eyebrow']))}</p>
        <h1>{escape(str(text['h1']))}</h1>
        <p class="lede">{escape(str(text['lede']))}</p>
      </div>
      <dl class="stats" aria-label="Index summary">
        <div><dt>{escape(str(text['pages']))}</dt><dd>{len(index.pages)}</dd></div>
        <div><dt>{escape(str(text['words']))}</dt><dd>{len(index.words)}</dd></div>
        <div><dt>{escape(str(text['query']))}</dt><dd>{escape(query or str(text['empty']))}</dd></div>
      </dl>
    </header>
    """


def _pipeline(text: dict[str, object]) -> str:
    steps = text["pipeline_steps"]
    assert isinstance(steps, list)
    items = "".join(f'<li><span>{index}</span>{escape(step)}</li>' for index, step in enumerate(steps, 1))
    return f"""
    <section class="band">
      <h2>{escape(str(text['data_pipeline']))}</h2>
      <ol class="pipeline">{items}</ol>
    </section>
    """


def _query_form(query: str, lang: str, text: dict[str, object]) -> str:
    en_selected = " selected" if lang == "en" else ""
    zh_selected = " selected" if lang == "zh" else ""
    return f"""
    <section class="band controls">
      <form method="get" action="/">
        <label for="q">{escape(str(text['query_trace']))}</label>
        <input id="q" name="q" value="{escape(query)}" autocomplete="off">
        <label for="lang">{escape(str(text['language']))}</label>
        <select id="lang" name="lang">
          <option value="en"{en_selected}>{escape(str(text['english']))}</option>
          <option value="zh"{zh_selected}>{escape(str(text['chinese']))}</option>
        </select>
        <button type="submit">{escape(str(text['update']))}</button>
      </form>
    </section>
    """


def _saved_index_note(text: dict[str, object]) -> str:
    return f"""
    <section class="band">
      <p class="section-note">{escape(str(text['saved_index_note']))}</p>
    </section>
    """


def _page_flow(pages: list[PageDocument], text: dict[str, object]) -> str:
    rendered_pages = []
    for page in pages:
        quotes = extract_quotes(page.html)
        searchable_text = extract_searchable_text(page.html)
        tokens = tokenize(searchable_text)
        quote_items = "".join(
            f"""
            <li>
              <strong>{escape(quote.text or str(text['missing_text']))}</strong>
              <span>{escape(str(text['author']))}: {escape(quote.author or str(text['missing']))}</span>
              <span>{escape(str(text['tags']))}: {escape(", ".join(quote.tags) if quote.tags else str(text['none']))}</span>
            </li>
            """
            for quote in quotes
        )
        token_items = "".join(
            f'<span class="token"><small>{position}</small>{escape(token)}</span>'
            for position, token in enumerate(tokens)
        )
        rendered_pages.append(
            f"""
            <article class="page-block">
              <div class="page-head">
                <h3>{escape(page.url)}</h3>
                <span>{escape(extract_title(page.html) or str(text['no_title']))}</span>
              </div>
              <details>
                <summary>{escape(str(text['demo_html']))}</summary>
                <pre>{escape(page.html.strip())}</pre>
              </details>
              <h4>{escape(str(text['quote_records']))}</h4>
              <ul class="quotes">{quote_items}</ul>
              <h4>{escape(str(text['pipeline_steps'][2]))}</h4>
              <p class="searchable">{escape(searchable_text or str(text['empty']))}</p>
              <h4>{escape(str(text['tokens_with_positions']))}</h4>
              <div class="tokens">{token_items}</div>
            </article>
            """
        )

    return f"""
    <section class="band">
      <h2>{escape(str(text['extraction']))}</h2>
      <div class="page-grid">{''.join(rendered_pages)}</div>
    </section>
    """


def _build_flow(events: list[BuildEvent], text: dict[str, object]) -> str:
    rows = "".join(
        f"""
        <tr>
          <td>{escape(event.page_url)}</td>
          <td>{event.position}</td>
          <td><span class="word">{escape(event.token)}</span></td>
          <td><span class="badge {event.word_action}">{event.word_action}</span></td>
          <td><span class="badge {event.page_action}">{event.page_action}</span></td>
          <td>{event.before_frequency} -> {event.after_frequency}</td>
          <td>{escape(str(list(event.positions)))}</td>
        </tr>
        """
        for event in events
    )
    return f"""
    <section class="band">
      <h2>{escape(str(text['build_trace']))}</h2>
      <p class="section-note">{escape(str(text['build_note']))}</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{escape(str(text['page']))}</th><th>{escape(str(text['position']))}</th><th>{escape(str(text['token']))}</th><th>{escape(str(text['word_entry']))}</th>
              <th>{escape(str(text['page_stats']))}</th><th>{escape(str(text['frequency']))}</th><th>{escape(str(text['positions']))}</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>
    """


def _index_view(index: InvertedIndex, text: dict[str, object]) -> str:
    rows = []
    for word, page_entries in sorted(index.words.items()):
        pages = "".join(
            f"""
            <li>
              <span>{escape(url)}</span>
              <code>frequency={stats.frequency}</code>
              <code>positions={escape(str(stats.positions))}</code>
            </li>
            """
            for url, stats in sorted(page_entries.items())
        )
        rows.append(f"<article class=\"index-row\"><h3>{escape(word)}</h3><ul>{pages}</ul></article>")

    return f"""
    <section class="band">
      <h2>{escape(str(text['inverted_index']))}</h2>
      <div class="index-list">{''.join(rows)}</div>
    </section>
    """


def _query_view(
    index: InvertedIndex,
    query: str,
    query_tokens: list[str],
    matching_pages: list[str],
    text: dict[str, object],
) -> str:
    if not query_tokens:
        return f"""
        <section class="band">
          <h2>{escape(str(text['query_intersection']))}</h2>
          <p class="section-note">{escape(str(text['no_valid_tokens']))}</p>
        </section>
        """

    token_sets = []
    page_sets: list[set[str]] = []
    for token in query_tokens:
        pages = set(index.words.get(token, {}))
        page_sets.append(pages)
        page_items = "".join(f"<li>{escape(url)}</li>" for url in sorted(pages)) or f"<li>{escape(str(text['none']))}</li>"
        token_sets.append(
            f"""
            <article class="set-block">
              <h3>{escape(token)}</h3>
              <ul>{page_items}</ul>
            </article>
            """
        )

    intersections = []
    current = page_sets[0]
    intersections.append(f"Start: {_format_set(current)}")
    for token, pages in zip(query_tokens[1:], page_sets[1:]):
        before = set(current)
        current = current.intersection(pages)
        intersections.append(
            f"{_format_set(before)} AND {escape(token)} {_format_set(pages)} = {_format_set(current)}"
        )

    steps = "".join(f"<li>{step}</li>" for step in intersections)
    ranked_results = {result.url: result for result in ranked_search(index, query)}
    matches = "".join(
        f"""
        <li>
          <strong>{escape(url)}</strong>
          <span>{escape(ranked_results[url].snippet) if url in ranked_results else ""}</span>
        </li>
        """
        for url in matching_pages
    ) or f"<li>{escape(str(text['no_matches']))}</li>"
    return f"""
    <section class="band">
      <h2>{escape(str(text['query_intersection']))}</h2>
      <p class="section-note">{escape(str(text['normalized_query']))}: {' '.join(escape(token) for token in query_tokens)}</p>
      <div class="set-grid">{''.join(token_sets)}</div>
      <ol class="intersection">{steps}</ol>
      <h3>{escape(str(text['final_result']))}</h3>
      <ul class="results">{matches}</ul>
    </section>
    """


def _format_set(values: set[str]) -> str:
    if not values:
        return "{}"
    return "{" + ", ".join(escape(value) for value in sorted(values)) + "}"


def _css() -> str:
    return """
    :root {
      color-scheme: light;
      --ink: #172026;
      --muted: #5c6870;
      --line: #d7dde2;
      --paper: #ffffff;
      --soft: #f3f6f8;
      --green: #1f7a5c;
      --blue: #2f5f9e;
      --amber: #9a6400;
      --rose: #a33b4f;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--soft);
      line-height: 1.5;
    }
    .shell { max-width: 1180px; margin: 0 auto; padding: 24px; }
    .top {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 24px;
      align-items: end;
      padding: 20px 0 18px;
      border-bottom: 2px solid var(--ink);
    }
    .eyebrow { margin: 0 0 4px; color: var(--green); font-weight: 700; }
    h1, h2, h3, h4, p { margin-top: 0; }
    h1 { margin-bottom: 8px; font-size: 34px; }
    h2 { margin-bottom: 14px; font-size: 22px; }
    h3 { font-size: 16px; }
    h4 { margin: 16px 0 8px; color: var(--muted); font-size: 13px; text-transform: uppercase; }
    .lede { max-width: 680px; margin-bottom: 0; color: var(--muted); }
    .stats { display: grid; grid-template-columns: repeat(3, minmax(90px, 1fr)); gap: 8px; margin: 0; }
    .stats div, .band, .page-block, .set-block, .index-row {
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    .stats div { padding: 12px; }
    dt { color: var(--muted); font-size: 12px; }
    dd { margin: 0; font-weight: 700; }
    .band { margin-top: 18px; padding: 18px; }
    .section-note { color: var(--muted); }
    .pipeline {
      display: grid;
      grid-template-columns: repeat(5, minmax(120px, 1fr));
      gap: 10px;
      padding: 0;
      margin: 0;
      list-style: none;
    }
    .pipeline li {
      min-height: 64px;
      padding: 12px;
      border: 1px solid var(--line);
      border-left: 4px solid var(--blue);
      background: #f8fafc;
      font-weight: 700;
    }
    .pipeline span { display: block; color: var(--blue); font-size: 12px; }
    .controls form { display: grid; grid-template-columns: auto 1fr auto auto auto; gap: 10px; align-items: center; }
    label { font-weight: 700; }
    input, select, button {
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      font: inherit;
    }
    input, select { padding: 8px 10px; background: white; }
    button { padding: 8px 14px; background: var(--ink); color: white; cursor: pointer; }
    .page-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
    .page-block, .set-block, .index-row { padding: 14px; }
    .page-head { display: flex; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--line); padding-bottom: 8px; }
    .page-head h3 { margin: 0; overflow-wrap: anywhere; }
    .page-head span { color: var(--muted); }
    details { margin-top: 12px; }
    summary { cursor: pointer; color: var(--blue); font-weight: 700; }
    pre {
      max-height: 220px;
      overflow: auto;
      padding: 10px;
      background: #111820;
      color: #eef4f8;
      border-radius: 6px;
      font-size: 12px;
    }
    .quotes { padding-left: 18px; }
    .quotes span { display: block; color: var(--muted); }
    .searchable { padding: 10px; border-left: 4px solid var(--green); background: #f4fbf7; }
    .tokens { display: flex; flex-wrap: wrap; gap: 8px; }
    .token, .word {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 8px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fffaf0;
    }
    .token small { color: var(--amber); font-weight: 700; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; min-width: 820px; }
    th, td { padding: 9px 8px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
    th { background: #eef3f6; font-size: 12px; text-transform: uppercase; }
    .badge { display: inline-block; min-width: 54px; padding: 3px 7px; border-radius: 6px; text-align: center; font-weight: 700; }
    .badge.create { background: #e6f4ed; color: var(--green); }
    .badge.reuse { background: #eef2ff; color: var(--blue); }
    .index-list { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
    .index-row h3 { margin-bottom: 8px; color: var(--rose); }
    .index-row ul, .set-block ul, .results { margin: 0; padding-left: 18px; }
    code { display: inline-block; margin: 3px 4px 0 0; color: var(--muted); }
    .set-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
    .intersection { margin-bottom: 16px; }
    .results li { font-weight: 700; }
    .results span { display: block; color: var(--muted); font-weight: 400; }
    @media (max-width: 820px) {
      .shell { padding: 14px; }
      .top, .page-grid, .index-list, .set-grid, .pipeline { grid-template-columns: 1fr; }
      .stats { grid-template-columns: 1fr; }
      .controls form { grid-template-columns: 1fr; }
    }
    """


if __name__ == "__main__":
    main()
