import json
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SocialPoster/1.0)"}
_TIMEOUT = 10

# Hosts to exclude from Mastodon detection
_NON_FEDI_HOSTS = [
    "linkedin.com", "bsky", "youtube", "discord", "roblox",
    "stackoverflow", "vimeo", "discourse", "x.com", "twitter",
]


def _is_mastodon(parsed):
    """Heuristic for Mastodon-like profile URLs."""
    path = parsed.path
    host = parsed.hostname or ""
    if not (path.startswith("/@") or path.startswith("/users/")):
        return False
    for excluded in _NON_FEDI_HOSTS:
        if excluded in host:
            return False
    return True


def _is_bluesky(parsed):
    """Detect Bluesky profile URLs."""
    return "bsky" in (parsed.hostname or "")


def _to_absolute(href, base):
    """Resolve a possibly-relative URL against a base."""
    try:
        parsed = urlparse(href)
        if parsed.scheme:
            return href
        base_parsed = urlparse(base)
        if href.startswith("/"):
            return f"{base_parsed.scheme}://{base_parsed.netloc}{href}"
        return f"{base.rstrip('/')}/{href}"
    except Exception:
        return None


def _extract_from_html(html, origin):
    """Extract Mastodon and Bluesky profile URLs from HTML content."""
    soup = BeautifulSoup(html, "html.parser")
    found = {"mastodon": [], "bluesky": []}

    # Strategy 1: JSON-LD sameAs
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            graph = data if isinstance(data, list) else [data]
            for node in graph:
                same_as = node.get("sameAs") if isinstance(node, dict) else None
                if not same_as:
                    continue
                links = same_as if isinstance(same_as, list) else [same_as]
                for href in links:
                    abs_url = _to_absolute(href, origin)
                    if not abs_url:
                        continue
                    parsed = urlparse(abs_url)
                    if _is_bluesky(parsed):
                        found["bluesky"].append(abs_url)
                    elif _is_mastodon(parsed):
                        found["mastodon"].append(abs_url)
        except (json.JSONDecodeError, TypeError):
            continue

    # Strategy 2: anchor tags
    for a in soup.find_all("a", href=True):
        href = a["href"]
        abs_url = _to_absolute(href, origin)
        if not abs_url:
            continue
        try:
            parsed = urlparse(abs_url)
        except Exception:
            continue

        # 2a: rel="me" links
        rel = (a.get("rel") or [])
        if isinstance(rel, list):
            rel_str = " ".join(rel).lower()
        else:
            rel_str = str(rel).lower()

        if "me" in rel_str.split():
            if _is_bluesky(parsed):
                found["bluesky"].append(abs_url)
            elif _is_mastodon(parsed):
                found["mastodon"].append(abs_url)
            continue

        # 2b: URL pattern matching
        if _is_bluesky(parsed):
            found["bluesky"].append(abs_url)
        elif _is_mastodon(parsed):
            found["mastodon"].append(abs_url)

        # 2c: CSS class / aria-label / title hints
        css_class = (a.get("class") or [])
        if isinstance(css_class, list):
            css_class = " ".join(css_class).lower()
        else:
            css_class = str(css_class).lower()
        label = (a.get("aria-label") or a.get("title") or a.get_text() or "").lower()

        if ("mastodon" in css_class or "mastodon" in label) and _is_mastodon(parsed):
            found["mastodon"].append(abs_url)
        if ("bluesky" in css_class or "bsky" in css_class or "bluesky" in label) and _is_bluesky(parsed):
            found["bluesky"].append(abs_url)

    # Deduplicate
    found["mastodon"] = list(dict.fromkeys(found["mastodon"]))
    found["bluesky"] = list(dict.fromkeys(found["bluesky"]))

    return found


def _url_to_mastodon_mention(url):
    """Convert https://instance.social/@user to @user@instance.social"""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    path = parsed.path.rstrip("/")
    if path.startswith("/@"):
        user = path[2:]  # strip /@
        # Remove anything after a slash (e.g. /@user/123)
        user = user.split("/")[0]
        return f"@{user}@{host}"
    if path.startswith("/users/"):
        user = path[7:]  # strip /users/
        user = user.split("/")[0]
        return f"@{user}@{host}"
    return ""


def _url_to_bluesky_mention(url):
    """Convert https://bsky.app/profile/handle to @handle"""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    match = re.match(r"^/profile/(.+)$", path)
    if match:
        handle = match.group(1).split("/")[0]
        return f"@{handle}"
    return ""


def _fetch_page(url):
    """Fetch a page's HTML, returning empty string on failure."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return ""


def extract_social_links(url):
    """Extract Mastodon and Bluesky mentions from a website.

    Checks homepage, /about/, and /en/ pages.
    Returns {"mastodon": "@user@instance" or "", "bluesky": "@handle" or ""}.
    """
    try:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return {"mastodon": "", "bluesky": ""}

    pages_to_check = [
        origin,
        f"{origin}/about/",
        f"{origin}/en/",
    ]

    combined = {"mastodon": [], "bluesky": []}

    for page_url in pages_to_check:
        html = _fetch_page(page_url)
        if not html:
            continue

        page_results = _extract_from_html(html, origin)

        # Prepend page results (later pages like /about/ get priority)
        combined["mastodon"] = page_results["mastodon"] + combined["mastodon"]
        combined["bluesky"] = page_results["bluesky"] + combined["bluesky"]

        # Stop early after /about/ if we found anything
        if page_url.rstrip("/").endswith("/about"):
            if combined["mastodon"] or combined["bluesky"]:
                break

    # Deduplicate
    combined["mastodon"] = list(dict.fromkeys(combined["mastodon"]))
    combined["bluesky"] = list(dict.fromkeys(combined["bluesky"]))

    # Convert first URL of each platform to a mention
    mastodon_mention = ""
    if combined["mastodon"]:
        mastodon_mention = _url_to_mastodon_mention(combined["mastodon"][0])

    bluesky_mention = ""
    if combined["bluesky"]:
        bluesky_mention = _url_to_bluesky_mention(combined["bluesky"][0])

    return {"mastodon": mastodon_mention, "bluesky": bluesky_mention}
