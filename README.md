# CW2 Search Tool

This project is a Python command-line search tool for
`https://quotes.toscrape.com/`. It will crawl the quote listing pages, build an
inverted index, save and load that index, and allow users to search it from an
interactive shell.

## Current Status

The repository currently includes the required project structure and a polite
crawler that follows the quote pagination links while staying inside the target
domain.

## Setup

Create and activate a virtual environment, then install the dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Project Structure

```text
src/
  crawler.py
  indexer.py
  search.py
  main.py
tests/
  test_crawler.py
  test_indexer.py
  test_search.py
data/
requirements.txt
README.md
```

## Running Tests

```bash
pytest
```

To include coverage:

```bash
pytest --cov=src
```

## Planned Commands

The final interactive shell will support:

```text
build
load
print nonsense
find indifference
find good friends
```

The crawler observes a minimum 6 second politeness window between successive
real requests. Tests use mocks so they do not wait or depend on live network
access.
