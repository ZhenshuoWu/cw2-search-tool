from src.indexer import (
    PageDocument,
    QuoteRecord,
    build_inverted_index,
    extract_quotes,
    extract_searchable_text,
    lookup_word,
    tokenize,
)


def test_extract_quotes_returns_text_author_and_tags():
    html = """
    <html>
      <body>
        <div class="quote">
          <span class="text">The world as we have created it.</span>
          <small class="author">Albert Einstein</small>
          <div class="tags">
            <a class="tag">change</a>
            <a class="tag">deep-thoughts</a>
          </div>
        </div>
        <div class="quote">
          <span class="text">It is our choices.</span>
          <small class="author">J.K. Rowling</small>
          <div class="tags">
            <a class="tag">abilities</a>
            <a class="tag">choices</a>
          </div>
        </div>
      </body>
    </html>
    """

    quotes = extract_quotes(html)

    assert quotes == [
        QuoteRecord(
            text="The world as we have created it.",
            author="Albert Einstein",
            tags=("change", "deep-thoughts"),
        ),
        QuoteRecord(
            text="It is our choices.",
            author="J.K. Rowling",
            tags=("abilities", "choices"),
        ),
    ]


def test_extract_searchable_text_combines_quote_fields():
    html = """
    <div class="quote">
      <span class="text">A day without sunshine.</span>
      <small class="author">Steve Martin</small>
      <div class="tags"><a class="tag">humor</a></div>
    </div>
    """

    text = extract_searchable_text(html)

    assert text == "A day without sunshine. Steve Martin humor"


def test_extract_quotes_collapses_nested_whitespace():
    html = """
    <div class="quote">
      <span class="text">
        A     quote
        with <strong>nested</strong> text.
      </span>
      <small class="author">  Jane   Doe  </small>
      <div class="tags">
        <a class="tag">  spaced   tag  </a>
      </div>
    </div>
    """

    quotes = extract_quotes(html)

    assert quotes == [
        QuoteRecord(
            text="A quote with nested text.",
            author="Jane Doe",
            tags=("spaced tag",),
        )
    ]


def test_extract_quotes_handles_empty_html_and_missing_quote_blocks():
    assert extract_quotes("") == []
    assert extract_quotes("<html><body><p>No quotes here</p></body></html>") == []
    assert extract_searchable_text("") == ""


def test_extract_quotes_handles_missing_fields_without_error():
    html = """
    <div class="quote">
      <span class="text">Only quote text is available.</span>
    </div>
    <div class="quote">
      <small class="author">Only Author</small>
      <div class="tags"><a class="tag">solo</a></div>
    </div>
    <div class="quote"></div>
    """

    quotes = extract_quotes(html)

    assert quotes == [
        QuoteRecord(text="Only quote text is available.", author="", tags=()),
        QuoteRecord(text="", author="Only Author", tags=("solo",)),
    ]


def test_tokenize_normalizes_case_and_ignores_punctuation():
    tokens = tokenize("Good, good! GOOD friends. deep-thoughts")

    assert tokens == ["good", "good", "good", "friends", "deep", "thoughts"]


def test_tokenize_ignores_empty_whitespace_and_punctuation_only_input():
    assert tokenize("") == []
    assert tokenize("   ") == []
    assert tokenize("...!?") == []


def test_build_inverted_index_records_frequency_positions_and_page_metadata():
    pages = [
        PageDocument(
            url="https://quotes.toscrape.com/",
            html="""
            <html>
              <head><title>Quotes Page One</title></head>
              <body>
                <div class="quote">
                  <span class="text">Good friends are good.</span>
                  <small class="author">Alice</small>
                  <div class="tags"><a class="tag">Friendship</a></div>
                </div>
              </body>
            </html>
            """,
        ),
        PageDocument(
            url="https://quotes.toscrape.com/page/2/",
            html="""
            <div class="quote">
              <span class="text">Indifference is not good.</span>
              <small class="author">Bob</small>
            </div>
            """,
        ),
    ]

    index = build_inverted_index(pages)

    assert index.pages["https://quotes.toscrape.com/"].title == "Quotes Page One"
    assert index.pages["https://quotes.toscrape.com/"].word_count == 6
    assert index.pages["https://quotes.toscrape.com/"].quote_count == 1
    assert index.pages["https://quotes.toscrape.com/"].searchable_text == (
        "Good friends are good. Alice Friendship"
    )
    assert index.words["good"]["https://quotes.toscrape.com/"].frequency == 2
    assert index.words["good"]["https://quotes.toscrape.com/"].positions == [0, 3]
    assert index.words["good"]["https://quotes.toscrape.com/page/2/"].frequency == 1
    assert index.words["friends"]["https://quotes.toscrape.com/"].positions == [1]
    assert index.words["indifference"]["https://quotes.toscrape.com/page/2/"].positions == [
        0
    ]


def test_lookup_word_is_case_insensitive_and_returns_empty_for_missing_words():
    index = build_inverted_index(
        [
            PageDocument(
                url="https://quotes.toscrape.com/",
                html='<div class="quote"><span class="text">Good friends.</span></div>',
            )
        ]
    )

    assert lookup_word(index, "GOOD") == index.words["good"]
    assert lookup_word(index, "missing") == {}
    assert lookup_word(index, "") == {}
    assert lookup_word(index, "good friends") == {}
