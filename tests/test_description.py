import responses

from services.description import extract_description


def _html(body):
    return f"<html><head>{body}</head><body></body></html>"


@responses.activate
def test_meta_description():
    html = _html('<meta name="description" content="Hello world">')
    responses.add(responses.GET, "https://example.com", body=html)
    assert extract_description("https://example.com") == "Hello world"


@responses.activate
def test_og_description():
    html = _html('<meta property="og:description" content="OG desc">')
    responses.add(responses.GET, "https://example.com", body=html)
    assert extract_description("https://example.com") == "OG desc"


@responses.activate
def test_twitter_card_description():
    html = _html('<meta name="twitter:description" content="Twitter desc">')
    responses.add(responses.GET, "https://example.com", body=html)
    assert extract_description("https://example.com") == "Twitter desc"


@responses.activate
def test_dublin_core_description():
    html = _html('<meta name="DC.description" content="DC desc">')
    responses.add(responses.GET, "https://example.com", body=html)
    assert extract_description("https://example.com") == "DC desc"


@responses.activate
def test_schema_microdata_description():
    html = _html('<meta itemprop="description" content="Schema desc">')
    responses.add(responses.GET, "https://example.com", body=html)
    assert extract_description("https://example.com") == "Schema desc"


@responses.activate
def test_json_ld_description():
    html = _html(
        '<script type="application/ld+json">'
        '{"description": "JSON-LD desc"}'
        "</script>"
    )
    responses.add(responses.GET, "https://example.com", body=html)
    assert extract_description("https://example.com") == "JSON-LD desc"


@responses.activate
def test_json_ld_graph_description():
    html = _html(
        '<script type="application/ld+json">'
        '{"@graph": [{"@type": "WebPage", "description": "Graph desc"}]}'
        "</script>"
    )
    responses.add(responses.GET, "https://example.com", body=html)
    assert extract_description("https://example.com") == "Graph desc"


@responses.activate
def test_sanitize_html_tags():
    html = _html('<meta name="description" content="Hello <b>world</b>">')
    responses.add(responses.GET, "https://example.com", body=html)
    result = extract_description("https://example.com")
    assert "<" not in result
    assert ">" not in result


@responses.activate
def test_sanitize_ampersand_not_double_escaped():
    html = _html('<meta name="description" content="A &amp; B &amp; C">')
    responses.add(responses.GET, "https://example.com", body=html)
    result = extract_description("https://example.com")
    # &amp; from HTML is decoded to & by BS4, then re-encoded to &amp;
    assert "&amp;amp;" not in result


@responses.activate
def test_sanitize_quotes():
    html = _html('<meta name="description" content="She said &quot;hello&quot;">')
    responses.add(responses.GET, "https://example.com", body=html)
    result = extract_description("https://example.com")
    assert "&quot;" in result


@responses.activate
def test_sanitize_control_chars():
    html = _html('<meta name="description" content="Hello\x00World\x1f">')
    responses.add(responses.GET, "https://example.com", body=html)
    result = extract_description("https://example.com")
    assert "\x00" not in result
    assert "\x1f" not in result


@responses.activate
def test_sanitize_zero_width_chars():
    html = _html('<meta name="description" content="Hello\u200bWorld">')
    responses.add(responses.GET, "https://example.com", body=html)
    result = extract_description("https://example.com")
    assert "\u200b" not in result


@responses.activate
def test_truncate_300_chars():
    long_desc = "A" * 500
    html = _html(f'<meta name="description" content="{long_desc}">')
    responses.add(responses.GET, "https://example.com", body=html)
    result = extract_description("https://example.com")
    assert len(result) == 300


@responses.activate
def test_markdown_link_conversion():
    html = _html('<meta name="description" content="Check [my site](https://example.com)">')
    responses.add(responses.GET, "https://example.com", body=html)
    result = extract_description("https://example.com")
    assert '<a href="https://example.com">my site</a>' in result


def test_youtube_short_circuit():
    assert extract_description("https://youtube.com/watch?v=123") == "YouTube video"


@responses.activate
def test_network_failure_returns_empty():
    responses.add(responses.GET, "https://example.com", body=Exception("Connection error"))
    assert extract_description("https://example.com") == ""


@responses.activate
def test_no_description_returns_empty():
    html = _html("<title>Just a title</title>")
    responses.add(responses.GET, "https://example.com", body=html)
    assert extract_description("https://example.com") == ""


@responses.activate
def test_meta_description_priority_over_og():
    html = _html(
        '<meta name="description" content="Meta desc">'
        '<meta property="og:description" content="OG desc">'
    )
    responses.add(responses.GET, "https://example.com", body=html)
    assert extract_description("https://example.com") == "Meta desc"
