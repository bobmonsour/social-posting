import responses

from services.link_card import fetch_og_metadata


@responses.activate
def test_og_metadata_extraction():
    html = '''
    <html><head>
    <meta property="og:title" content="Test Title">
    <meta property="og:description" content="Test Description">
    <meta property="og:image" content="https://example.com/img.jpg">
    </head></html>
    '''
    responses.add(responses.GET, "https://example.com", body=html)
    responses.add(responses.GET, "https://example.com/img.jpg",
                  body=b"\xff\xd8\xff\xe0", content_type="image/jpeg")
    card = fetch_og_metadata("https://example.com")
    assert card.title == "Test Title"
    assert card.description == "Test Description"
    assert card.image_url == "https://example.com/img.jpg"


@responses.activate
def test_fallback_to_soup_title():
    html = '<html><head><title>Page Title</title></head></html>'
    responses.add(responses.GET, "https://example.com", body=html)
    card = fetch_og_metadata("https://example.com")
    assert card.title == "Page Title"


@responses.activate
def test_name_attr_fallback():
    html = '''
    <html><head>
    <meta name="og:title" content="Name Attr Title">
    <meta name="og:description" content="Name Attr Desc">
    </head></html>
    '''
    responses.add(responses.GET, "https://example.com", body=html)
    card = fetch_og_metadata("https://example.com")
    assert card.title == "Name Attr Title"
    assert card.description == "Name Attr Desc"


@responses.activate
def test_relative_image_url():
    html = '''
    <html><head>
    <meta property="og:title" content="T">
    <meta property="og:image" content="/images/pic.jpg">
    </head></html>
    '''
    responses.add(responses.GET, "https://example.com", body=html)
    responses.add(responses.GET, "https://example.com/images/pic.jpg",
                  body=b"\xff\xd8", content_type="image/jpeg")
    card = fetch_og_metadata("https://example.com")
    assert card.image_url == "https://example.com/images/pic.jpg"
    assert card.image_data == b"\xff\xd8"


@responses.activate
def test_network_failure():
    responses.add(responses.GET, "https://fail.com", body=Exception("Network error"))
    card = fetch_og_metadata("https://fail.com")
    assert card.url == "https://fail.com"
    assert "Network error" in card.description


@responses.activate
def test_no_og_returns_empty_fields():
    html = "<html><head></head><body></body></html>"
    responses.add(responses.GET, "https://example.com", body=html)
    card = fetch_og_metadata("https://example.com")
    assert card.title == ""
    assert card.description == ""
    assert card.image_url == ""
