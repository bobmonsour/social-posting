from urllib.parse import urlparse

import requests


def check_leaderboard_link(url):
    """Check if a site appears on the 11ty Speedlify Leaderboard.

    Normalizes the domain and probes the leaderboard URL with variations.
    Returns the leaderboard URL string if found, or None.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.netloc or parsed.path
    except Exception:
        return None

    if not hostname:
        return None

    # Strip www. prefix
    bare = hostname.lower().removeprefix("www.")

    # Normalize: replace dots and slashes with hyphens
    slug = bare.replace(".", "-").replace("/", "-").rstrip("-")

    # Try variations: bare domain and with www
    candidates = [slug]
    www_slug = "www-" + slug
    if not hostname.lower().startswith("www."):
        candidates.append(www_slug)
    else:
        candidates.insert(0, www_slug)

    base = "https://www.11ty.dev/speedlify/"

    for candidate in candidates:
        for suffix in ["", "/"]:
            probe_url = base + candidate + suffix
            try:
                resp = requests.head(probe_url, timeout=10, allow_redirects=True)
                if resp.status_code == 200:
                    return base + candidate + "/"
            except Exception:
                continue

    return None
