"""Command-line entry point for the CW2 search tool."""

from __future__ import annotations

import cmd
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

from src.crawler import WebsiteCrawler
from src.indexer import InvertedIndex, PageDocument, build_inverted_index
from src.search import (
    format_find_results,
    format_index_summary,
    format_word_entry,
)
from src.storage import (
    DEFAULT_INDEX_PATH,
    DEFAULT_REPORT_PATH,
    load_index,
    save_crawl_report,
    save_index,
)


class SearchShell(cmd.Cmd):
    """Interactive shell for the CW2 search tool."""

    intro = "CW2 search tool. Type help or exit."
    prompt = "> "

    def __init__(
        self,
        *,
        output: TextIO | None = None,
        pages_provider: Callable[[], list[PageDocument]] | None = None,
        crawler_factory: Callable[[], WebsiteCrawler] = WebsiteCrawler,
        index_path: Path | str = DEFAULT_INDEX_PATH,
        report_path: Path | str = DEFAULT_REPORT_PATH,
    ) -> None:
        super().__init__(stdout=output)
        self.index: InvertedIndex | None = None
        self.pages_provider = pages_provider
        self.crawler_factory = crawler_factory
        self.index_path = Path(index_path)
        self.report_path = Path(report_path)

    @property
    def index_loaded(self) -> bool:
        """Return True when the shell has an in-memory index."""

        return self.index is not None

    def emptyline(self) -> None:
        """Ignore empty input instead of repeating the previous command."""

        self._write("Please enter a command. Type help for options.")

    def default(self, line: str) -> None:
        """Handle unknown commands with a friendly message."""

        command = line.split(maxsplit=1)[0] if line.strip() else ""
        self._write(f"Unknown command: {command}. Type help for options.")

    def do_build(self, arg: str) -> None:
        """Crawl the target website, build the index, and save it to disk."""

        if self._has_extra_arguments("build", arg):
            return

        crawler: WebsiteCrawler | None = None
        if self.pages_provider is None:
            crawler = self.crawler_factory()
            crawled_pages = crawler.crawl()
            pages = [
                PageDocument(url=page.url, html=page.html)
                for page in crawled_pages
            ]
        else:
            pages = self.pages_provider()

        self.index = build_inverted_index(pages)
        index_path = save_index(self.index, self.index_path)
        self._write(format_index_summary(self.index))
        self._write(f"Saved index to {index_path}.")

        if crawler is not None:
            report_path = save_crawl_report(
                path=self.report_path,
                pages_crawled=len(pages),
                politeness_delay=crawler.politeness_delay,
                requests=crawler.requests,
                errors=crawler.errors,
            )
            self._write(
                f"Crawl report saved to {report_path}: "
                f"{len(crawler.requests)} requests, {len(crawler.errors)} errors."
            )

    def do_load(self, arg: str) -> None:
        """Load a saved index from disk."""

        if self._has_extra_arguments("load", arg):
            return
        try:
            self.index = load_index(self.index_path)
        except FileNotFoundError:
            self._write(f"No saved index found at {self.index_path}. Run build first.")
            return
        self._write(format_index_summary(self.index))
        self._write(f"Loaded index from {self.index_path}.")

    def do_print(self, arg: str) -> None:
        """Print the inverted index entry for one word."""

        word = arg.strip()
        if not word:
            self._write("Usage: print <word>")
            return
        if " " in word:
            self._write("Usage: print <word>")
            return
        if not self.index_loaded:
            self._write("No index loaded. Run build or load first.")
            return
        assert self.index is not None
        self._write(format_word_entry(self.index, word))

    def do_find(self, arg: str) -> None:
        """Find pages containing all query terms."""

        query = arg.strip()
        if not query:
            self._write("Usage: find <query terms>")
            return
        if not self.index_loaded:
            self._write("No index loaded. Run build or load first.")
            return
        assert self.index is not None
        self._write(format_find_results(self.index, query))

    def do_help(self, arg: str) -> None:
        """Show supported commands."""

        if arg.strip():
            super().do_help(arg)
            return

        self._write(
            "Commands: build, load, print <word>, find <query terms>, help, exit"
        )
        self._write('Tip: use quotes for exact phrases, e.g. find "good friends".')

    def do_exit(self, arg: str) -> bool:
        """Exit the shell."""

        if self._has_extra_arguments("exit", arg):
            return False
        self._write("Goodbye.")
        return True

    def do_quit(self, arg: str) -> bool:
        """Exit the shell."""

        return self.do_exit(arg)

    def do_EOF(self, arg: str) -> bool:
        """Exit cleanly when receiving end-of-file."""

        self._write("")
        return True

    def _has_extra_arguments(self, command: str, arg: str) -> bool:
        if not arg.strip():
            return False
        self._write(f"Usage: {command}")
        return True

    def _write(self, message: str) -> None:
        print(message, file=self.stdout)


def main() -> None:
    """Run the command-line program."""

    SearchShell().cmdloop()


if __name__ == "__main__":
    main()
