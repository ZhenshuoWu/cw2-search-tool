from io import StringIO

from src.indexer import PageDocument
from src.main import SearchShell
from src.search import demo_pages, find_pages, format_find_results, ranked_search, suggest_terms


def run_command(shell: SearchShell, command: str) -> str:
    output = StringIO()
    shell.stdout = output
    shell.onecmd(command)
    return output.getvalue()


def test_shell_help_lists_required_commands():
    shell = SearchShell(output=StringIO())

    output = run_command(shell, "help")

    assert "build" in output
    assert "load" in output
    assert "print <word>" in output
    assert "find <query terms>" in output


def test_shell_recognises_build_and_load_without_extra_arguments(tmp_path):
    index_path = tmp_path / "index.json"
    shell = SearchShell(
        output=StringIO(),
        pages_provider=demo_pages,
        index_path=index_path,
    )

    assert "Index ready" in run_command(shell, "build")

    loaded_shell = SearchShell(output=StringIO(), index_path=index_path)
    load_output = run_command(loaded_shell, "load")

    assert "Index ready" in load_output
    assert "Loaded index" in load_output


def test_shell_rejects_extra_arguments_for_build_and_load():
    shell = SearchShell(output=StringIO())

    assert "Usage: build" in run_command(shell, "build now")
    assert "Usage: load" in run_command(shell, "load data/index.json")


def test_shell_print_and_find_require_arguments():
    shell = SearchShell(output=StringIO())

    assert "Usage: print <word>" in run_command(shell, "print")
    assert "Usage: print <word>" in run_command(shell, "print good friends")
    assert "Usage: find <query terms>" in run_command(shell, "find")


def test_shell_print_and_find_prompt_to_load_index_first():
    shell = SearchShell(output=StringIO())

    assert "No index loaded" in run_command(shell, "print nonsense")
    assert "No index loaded" in run_command(shell, "find good friends")


def test_shell_build_print_and_find_run_closed_loop_on_demo_index(tmp_path):
    shell = SearchShell(
        output=StringIO(),
        pages_provider=demo_pages,
        index_path=tmp_path / "index.json",
    )

    build_output = run_command(shell, "build")
    print_output = run_command(shell, "print good")
    find_output = run_command(shell, "find good friends")

    assert "2 pages" in build_output
    assert "unique words" in build_output
    assert "Index entry for 'good'" in print_output
    assert "frequency=3" in print_output
    assert "positions=" in print_output
    assert "Pages matching good friends (ranked by BM25)" in find_output
    assert "score=" in find_output
    assert "snippet:" in find_output
    assert "demo://page-1" in find_output


def test_shell_can_build_from_injected_pages_for_tests(tmp_path):
    pages = [
        PageDocument(
            url="test://page",
            html='<div class="quote"><span class="text">Alpha beta alpha.</span></div>',
        )
    ]
    shell = SearchShell(
        output=StringIO(),
        pages_provider=lambda: pages,
        index_path=tmp_path / "index.json",
    )

    run_command(shell, "build")
    output = run_command(shell, "print alpha")

    assert "test://page" in output
    assert "frequency=2" in output


def test_find_pages_returns_multi_word_intersection_ranked_by_bm25(tmp_path):
    pages = [
        PageDocument(
            url="test://one",
            html='<div class="quote"><span class="text">Good friends good.</span></div>',
        ),
        PageDocument(
            url="test://two",
            html='<div class="quote"><span class="text">Good friends.</span></div>',
        ),
        PageDocument(
            url="test://three",
            html='<div class="quote"><span class="text">Good only.</span></div>',
        ),
    ]
    shell = SearchShell(
        output=StringIO(),
        pages_provider=lambda: pages,
        index_path=tmp_path / "index.json",
    )
    run_command(shell, "build")

    assert shell.index is not None
    assert find_pages(shell.index, "GOOD friends") == ["test://two", "test://one"]
    assert find_pages(shell.index, "missing friends") == []


def test_ranked_search_returns_scores_snippets_and_positions(tmp_path):
    pages = [
        PageDocument(
            url="test://strong",
            html='<div class="quote"><span class="text">Good friends good.</span></div>',
        ),
        PageDocument(
            url="test://weak",
            html='<div class="quote"><span class="text">Good friends.</span></div>',
        ),
    ]
    shell = SearchShell(
        output=StringIO(),
        pages_provider=lambda: pages,
        index_path=tmp_path / "index.json",
    )
    run_command(shell, "build")

    assert shell.index is not None
    results = ranked_search(shell.index, "good friends")

    assert [result.url for result in results] == ["test://strong", "test://weak"]
    assert results[0].score > results[1].score
    assert "[Good]" in results[0].snippet
    assert ("good", (0, 2)) in results[0].positions


def test_find_supports_exact_quoted_phrases(tmp_path):
    pages = [
        PageDocument(
            url="test://phrase",
            html='<div class="quote"><span class="text">Good friends stay.</span></div>',
        ),
        PageDocument(
            url="test://separate",
            html='<div class="quote"><span class="text">Good people become friends.</span></div>',
        ),
    ]
    shell = SearchShell(
        output=StringIO(),
        pages_provider=lambda: pages,
        index_path=tmp_path / "index.json",
    )
    run_command(shell, "build")

    assert shell.index is not None
    assert find_pages(shell.index, '"good friends"') == ["test://phrase"]


def test_find_results_suggest_close_terms_for_misspellings(tmp_path):
    shell = SearchShell(
        output=StringIO(),
        pages_provider=demo_pages,
        index_path=tmp_path / "index.json",
    )
    run_command(shell, "build")

    assert shell.index is not None
    assert suggest_terms(shell.index, "indiference") == {
        "indiference": ("indifference",)
    }

    output = format_find_results(shell.index, "indiference")

    assert "No pages found for: indiference" in output
    assert "Did you mean: indifference?" in output


def test_shell_handles_empty_unknown_and_exit_commands():
    shell = SearchShell(output=StringIO())

    empty_output = StringIO()
    shell.stdout = empty_output
    shell.emptyline()

    assert "Please enter a command" in empty_output.getvalue()
    assert "Unknown command" in run_command(shell, "wat")
    assert "Goodbye" in run_command(shell, "exit")
