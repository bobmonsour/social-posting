import responses

from services.rss_link import extract_rss_link, _looks_like_feed


# --- _looks_like_feed ---

def test_looks_like_feed_rss():
    assert _looks_like_feed('<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>')


def test_looks_like_feed_atom():
    assert _looks_like_feed('<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>')


def test_looks_like_feed_channel():
    assert _looks_like_feed('<channel><title>My Blog</title></channel>')


def test_looks_like_feed_rejects_html():
    assert not _looks_like_feed('<!DOCTYPE html><html><body>Not found</body></html>')


def test_looks_like_feed_rejects_html_with_rss_text():
    assert not _looks_like_feed('<html><body>This page is about <rss feeds</body></html>')


def test_looks_like_feed_empty():
    assert not _looks_like_feed('')


# --- extract_rss_link with link tags ---

@responses.activate
def test_extract_rss_link_from_link_tag():
    html = '''
    <html><head>
    <link type="application/rss+xml" href="https://example.com/feed.xml">
    </head></html>
    '''
    responses.add(responses.GET, "https://example.com", body=html)
    assert extract_rss_link("https://example.com/blog/post") == "https://example.com/feed.xml"


@responses.activate
def test_extract_atom_link_tag():
    html = '''
    <html><head>
    <link type="application/atom+xml" href="/atom.xml">
    </head></html>
    '''
    responses.add(responses.GET, "https://example.com", body=html)
    assert extract_rss_link("https://example.com/page") == "https://example.com/atom.xml"


@responses.activate
def test_extract_relative_href():
    html = '''
    <html><head>
    <link type="application/rss+xml" href="feed.xml">
    </head></html>
    '''
    responses.add(responses.GET, "https://example.com", body=html)
    assert extract_rss_link("https://example.com/page") == "https://example.com/feed.xml"


# --- extract_rss_link with feed path probing ---

@responses.activate
def test_extract_rss_link_probes_paths():
    # No link tag in homepage
    html = "<html><head></head></html>"
    responses.add(responses.GET, "https://example.com", body=html)
    # First probe returns feed
    feed_content = '<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
    responses.add(responses.GET, "https://example.com/feed.xml", body=feed_content)
    assert extract_rss_link("https://example.com/blog") == "https://example.com/feed.xml"


@responses.activate
def test_extract_rss_link_skips_html_error_pages():
    html = "<html><head></head></html>"
    responses.add(responses.GET, "https://example.com", body=html)
    # feed.xml returns HTML error
    responses.add(responses.GET, "https://example.com/feed.xml",
                  body="<!DOCTYPE html><html><body>404</body></html>")
    # rss.xml returns actual feed
    feed_content = '<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
    responses.add(responses.GET, "https://example.com/feed", body="<!DOCTYPE html><html>404</html>")
    responses.add(responses.GET, "https://example.com/rss.xml", body=feed_content)
    assert extract_rss_link("https://example.com/page") == "https://example.com/rss.xml"


@responses.activate
def test_extract_rss_link_network_failure():
    responses.add(responses.GET, "https://fail.com", body=Exception("Connection error"))
    assert extract_rss_link("https://fail.com/page") == ""
