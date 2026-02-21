from urllib.parse import urlparse

import responses

from services.social_links import (
    _is_mastodon,
    _is_bluesky,
    _url_to_mastodon_mention,
    _url_to_bluesky_mention,
    _extract_from_html,
    extract_social_links,
)


# --- _is_mastodon ---

def test_is_mastodon_at_path():
    parsed = urlparse("https://mastodon.social/@user")
    assert _is_mastodon(parsed)


def test_is_mastodon_users_path():
    parsed = urlparse("https://fosstodon.org/users/someone")
    assert _is_mastodon(parsed)


def test_is_mastodon_excluded_linkedin():
    parsed = urlparse("https://linkedin.com/@user")
    assert not _is_mastodon(parsed)


def test_is_mastodon_excluded_discord():
    parsed = urlparse("https://discord.com/@user")
    assert not _is_mastodon(parsed)


def test_is_mastodon_excluded_x():
    parsed = urlparse("https://x.com/@user")
    assert not _is_mastodon(parsed)


def test_is_mastodon_no_path():
    parsed = urlparse("https://mastodon.social/about")
    assert not _is_mastodon(parsed)


# --- _is_bluesky ---

def test_is_bluesky_positive():
    parsed = urlparse("https://bsky.app/profile/user.bsky.social")
    assert _is_bluesky(parsed)


def test_is_bluesky_negative():
    parsed = urlparse("https://example.com/profile/user")
    assert not _is_bluesky(parsed)


# --- _url_to_mastodon_mention ---

def test_mastodon_mention_at_format():
    assert _url_to_mastodon_mention("https://mastodon.social/@jane") == "@jane@mastodon.social"


def test_mastodon_mention_users_format():
    assert _url_to_mastodon_mention("https://fosstodon.org/users/bob") == "@bob@fosstodon.org"


def test_mastodon_mention_strips_subpath():
    assert _url_to_mastodon_mention("https://mastodon.social/@jane/123456") == "@jane@mastodon.social"


def test_mastodon_mention_users_strips_subpath():
    assert _url_to_mastodon_mention("https://fosstodon.org/users/bob/statuses/123") == "@bob@fosstodon.org"


def test_mastodon_mention_unknown_format():
    assert _url_to_mastodon_mention("https://example.com/about") == ""


# --- _url_to_bluesky_mention ---

def test_bluesky_mention_profile_format():
    assert _url_to_bluesky_mention("https://bsky.app/profile/jane.bsky.social") == "@jane.bsky.social"


def test_bluesky_mention_strips_subpath():
    assert _url_to_bluesky_mention("https://bsky.app/profile/jane.bsky.social/post/123") == "@jane.bsky.social"


def test_bluesky_mention_unknown_format():
    assert _url_to_bluesky_mention("https://bsky.app/about") == ""


# --- _extract_from_html ---

def test_extract_json_ld_same_as():
    html = '''
    <html><head>
    <script type="application/ld+json">
    {"sameAs": ["https://mastodon.social/@testuser", "https://bsky.app/profile/test.bsky.social"]}
    </script>
    </head><body></body></html>
    '''
    result = _extract_from_html(html, "https://example.com")
    assert "https://mastodon.social/@testuser" in result["mastodon"]
    assert "https://bsky.app/profile/test.bsky.social" in result["bluesky"]


def test_extract_rel_me_links():
    html = '''
    <html><body>
    <a href="https://mastodon.social/@user" rel="me">Mastodon</a>
    <a href="https://bsky.app/profile/user.bsky.social" rel="me">Bluesky</a>
    </body></html>
    '''
    result = _extract_from_html(html, "https://example.com")
    assert "https://mastodon.social/@user" in result["mastodon"]
    assert "https://bsky.app/profile/user.bsky.social" in result["bluesky"]


def test_extract_url_pattern_matching():
    html = '''
    <html><body>
    <a href="https://fosstodon.org/@dev">My Mastodon</a>
    </body></html>
    '''
    result = _extract_from_html(html, "https://example.com")
    assert "https://fosstodon.org/@dev" in result["mastodon"]


def test_extract_deduplicates():
    html = '''
    <html><body>
    <a href="https://mastodon.social/@user" rel="me">M</a>
    <a href="https://mastodon.social/@user">M again</a>
    </body></html>
    '''
    result = _extract_from_html(html, "https://example.com")
    assert len(result["mastodon"]) == 1


# --- extract_social_links (end-to-end) ---

@responses.activate
def test_extract_social_links_full():
    homepage = '<html><body><a href="https://mastodon.social/@dev" rel="me">M</a></body></html>'
    about = '<html><body><a href="https://bsky.app/profile/dev.bsky.social" rel="me">B</a></body></html>'

    responses.add(responses.GET, "https://example.com", body=homepage)
    responses.add(responses.GET, "https://example.com/about/", body=about)
    # /en/ should not be reached since /about/ found links
    responses.add(responses.GET, "https://example.com/en/", body="<html></html>")

    result = extract_social_links("https://example.com/page")
    assert result["mastodon"] == "@dev@mastodon.social"
    assert result["bluesky"] == "@dev.bsky.social"


@responses.activate
def test_extract_social_links_no_links():
    responses.add(responses.GET, "https://empty.com", body="<html></html>")
    responses.add(responses.GET, "https://empty.com/about/", body="<html></html>")
    responses.add(responses.GET, "https://empty.com/en/", body="<html></html>")

    result = extract_social_links("https://empty.com/page")
    assert result["mastodon"] == ""
    assert result["bluesky"] == ""


@responses.activate
def test_extract_social_links_about_early_stop():
    """If /about/ page has links, /en/ should NOT be fetched."""
    responses.add(responses.GET, "https://example.com", body="<html></html>")
    about_html = '<html><body><a href="https://mastodon.social/@found" rel="me">M</a></body></html>'
    responses.add(responses.GET, "https://example.com/about/", body=about_html)
    # Don't add /en/ — if it's requested, responses will raise ConnectionError

    result = extract_social_links("https://example.com/page")
    assert result["mastodon"] == "@found@mastodon.social"
    # Verify only 2 requests were made (homepage + /about/)
    assert len(responses.calls) == 2
