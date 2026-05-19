from src.indexer import QuoteRecord, extract_quotes, extract_searchable_text


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
