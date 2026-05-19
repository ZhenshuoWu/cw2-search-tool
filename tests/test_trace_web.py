from src.trace_web import collect_build_events, normalize_language, render_trace_page
from src.search import demo_pages


def test_collect_build_events_records_create_and_reuse_steps():
    events = collect_build_events(demo_pages())

    first_good = events[0]
    second_good = events[3]

    assert first_good.token == "good"
    assert first_good.word_action == "create"
    assert first_good.page_action == "create"
    assert first_good.before_frequency == 0
    assert first_good.after_frequency == 1
    assert first_good.positions == (0,)

    assert second_good.token == "good"
    assert second_good.word_action == "reuse"
    assert second_good.page_action == "reuse"
    assert second_good.before_frequency == 1
    assert second_good.after_frequency == 2
    assert second_good.positions == (0, 3)


def test_render_trace_page_contains_visual_sections_and_query_result():
    html = render_trace_page("good friends")

    assert "<!doctype html>" in html
    assert "Trace Visualizer" in html
    assert "Data Pipeline" in html
    assert "Extraction And Tokenization" in html
    assert "Build Trace" in html
    assert "Inverted Index" in html
    assert "Query Intersection" in html
    assert "demo://page-1" in html
    assert "frequency=3" in html
    assert "positions=[0, 3, 8]" in html
    assert "Good friends are good company." in html


def test_render_trace_page_supports_chinese_labels_and_language_select():
    html = render_trace_page("good friends", "zh")

    assert '<html lang="zh-CN">' in html
    assert "CW2 数据流可视化" in html
    assert "数据管线" in html
    assert "抽取与分词" in html
    assert "构建追踪" in html
    assert "倒排索引" in html
    assert "查询集合交集" in html
    assert '<option value="zh" selected>中文</option>' in html
    assert '<option value="en">English</option>' in html
    assert "demo://page-1" in html
    assert "frequency=3" in html


def test_render_trace_page_defaults_to_english_for_unknown_language():
    html = render_trace_page("good friends", "de")

    assert '<html lang="en">' in html
    assert "Trace Visualizer" in html
    assert normalize_language("de") == "en"


def test_render_trace_page_escapes_query_text():
    html = render_trace_page("<script>alert(1)</script>")

    assert "&lt;script&gt;alert" in html
    assert "<script>alert" not in html
    assert "No valid tokens" not in html
