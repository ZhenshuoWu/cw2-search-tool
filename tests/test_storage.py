from src.crawler import CrawlFailure, CrawlRequest
from src.indexer import PageDocument, build_inverted_index
from src.storage import load_index, save_crawl_report, save_index


def test_save_and_load_index_round_trip_preserves_statistics(tmp_path):
    index = build_inverted_index(
        [
            PageDocument(
                url="test://page",
                html='<div class="quote"><span class="text">Good good friends.</span></div>',
            )
        ]
    )
    index_path = tmp_path / "index.json"

    save_index(index, index_path)
    loaded = load_index(index_path)

    assert loaded.pages["test://page"].word_count == 3
    assert loaded.pages["test://page"].searchable_text == "Good good friends."
    assert loaded.words["good"]["test://page"].frequency == 2
    assert loaded.words["good"]["test://page"].positions == [0, 1]


def test_save_crawl_report_records_requests_and_errors(tmp_path):
    report_path = tmp_path / "crawl_report.json"

    save_crawl_report(
        path=report_path,
        pages_crawled=1,
        politeness_delay=6.0,
        requests=[
            CrawlRequest(
                requested_url="https://quotes.toscrape.com/",
                final_url="https://quotes.toscrape.com/",
                status_code=200,
                started_at=10.0,
                delay_seconds=0.0,
                accepted=True,
                reason="",
            )
        ],
        errors=[CrawlFailure(url="https://quotes.toscrape.com/page/2/", reason="timeout")],
    )

    text = report_path.read_text(encoding="utf-8")

    assert '"pages_crawled": 1' in text
    assert '"politeness_delay_seconds": 6.0' in text
    assert '"accepted": true' in text
    assert "timeout" in text
