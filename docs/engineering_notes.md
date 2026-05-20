# Engineering Notes

## Index Structure

The inverted index uses a nested dictionary:

```text
word -> page URL -> frequency and positions
```

This keeps `print <word>` as a direct lookup while allowing `find` to intersect
the page sets for each query token. Storing positions adds a little memory cost,
but it makes exact phrase checks and result explanations possible.

## Search Ranking

The required search behaviour is implemented first by finding pages that contain
all normalized query tokens. The final result list is then ordered with BM25 so
pages with stronger term evidence appear first.

This gives deterministic, explainable ranking without changing the coursework's
basic matching requirement.

## Benchmarking

`scripts/benchmark_search.py` creates synthetic quote-like pages and reports
median index build time and median ranked query time. The benchmark is local and
repeatable, so it avoids depending on live network speed or the target website.
