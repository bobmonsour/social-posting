import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

COMMON_FEED_PATHS = [
    "/feed.xml",
    "/feed",
    "/rss.xml",
    "/index.xml",
    "/atom.xml",
    "/feed/",
    "/blog/feed.xml",
    "/blog/feed",
    "/blog/rss.xml",
    "/blog/index.xml",
    "/blog/rss/",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SocialPoster/1.0)"}


def _looks_like_feed(content):
    """Check if content looks like an RSS/Atom feed (not an HTML error page)."""
    trimmed = content.lstrip()[:500]
    return (
        ("<rss" in trimmed or "<feed" in trimmed or "<channel>" in trimmed)
        and "<!DOCTYPE html" not in trimmed
        and "<html" not in trimmed
    )


def _probe_feed_paths(origin):
    """Probe common feed paths, return first valid feed URL or empty string."""
    for path in COMMON_FEED_PATHS:
        url = origin + path
        try:
            resp = requests.get(url, headers=HEADERS, timeout=3, allow_redirects=True)
            if resp.ok and _looks_like_feed(resp.text):
                return url
        except Exception:
            continue
    return ""


def extract_rss_link(url):
    """Extract RSS/Atom feed URL from a site.

    Mirrors the extraction logic from dbtools/lib/getrsslink.js.
    """
    try:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return ""

    try:
        resp = requests.get(origin, headers=HEADERS, timeout=10, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        rss_tag = soup.find("link", type="application/rss+xml") or \
                  soup.find("link", type="application/atom+xml")

        if rss_tag and rss_tag.get("href"):
            href = rss_tag["href"]
            if href.startswith("http"):
                return href
            elif href.startswith("/"):
                return origin + href
            else:
                return origin + "/" + href

        # No link tag found, probe common paths
        return _probe_feed_paths(origin)
    except Exception:
        return ""
