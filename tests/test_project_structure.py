from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_required_project_files_exist():
    required_paths = [
        ROOT / "src" / "crawler.py",
        ROOT / "src" / "indexer.py",
        ROOT / "src" / "search.py",
        ROOT / "src" / "main.py",
        ROOT / "tests" / "test_crawler.py",
        ROOT / "tests" / "test_indexer.py",
        ROOT / "tests" / "test_search.py",
        ROOT / "data",
        ROOT / "requirements.txt",
        ROOT / "README.md",
    ]

    missing = [str(path.relative_to(ROOT)) for path in required_paths if not path.exists()]

    assert missing == []


def test_readme_documents_dependency_installation():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "pip install -r requirements.txt" in readme
    assert "pytest" in readme


def test_requirements_include_runtime_and_test_dependencies():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "requests" in requirements
    assert "beautifulsoup4" in requirements
    assert "pytest" in requirements
