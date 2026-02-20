import os
import re
import shutil

import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO

FAVICON_STORAGE_DIR = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/favicons"
SITE_OUTPUT_DIR = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundle.dev/_site/img/favicons"
FAVICON_DB_PREFIX = "/img/favicons"
TARGET_SIZE = 64
FETCH_SIZE = 128

EXTENSIONS = [".png", ".jpg", ".jpeg", ".svg", ".ico", ".gif", ".webp"]


def slugify_domain(domain):
    """Slugify a domain name: lowercase, replace dots/special with hyphens."""
    slug = domain.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def _check_existing(domain_slug):
    """Check if a favicon already exists in storage for this domain."""
    for ext in EXTENSIONS:
        filename = f"{domain_slug}-favicon{ext}"
        path = os.path.join(FAVICON_STORAGE_DIR, filename)
        if os.path.exists(path):
            return path, filename
    return None, None


def _copy_to_site(filename):
    """Copy favicon to _site output directory if not already there."""
    src = os.path.join(FAVICON_STORAGE_DIR, filename)
    dest = os.path.join(SITE_OUTPUT_DIR, filename)
    if not os.path.exists(dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(src, dest)


def _save_favicon(data, filename, content_type=None):
    """Save favicon data, resize if needed, copy to both dirs."""
    ext = os.path.splitext(filename)[1].lower()
    storage_path = os.path.join(FAVICON_STORAGE_DIR, filename)
    os.makedirs(FAVICON_STORAGE_DIR, exist_ok=True)

    # For SVG and ICO, save as-is
    if ext in (".svg", ".ico"):
        with open(storage_path, "wb") as f:
            f.write(data)
    else:
        # Resize with Pillow
        try:
            img = Image.open(BytesIO(data))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGBA")
            else:
                img = img.convert("RGB")

            if img.size != (TARGET_SIZE, TARGET_SIZE):
                img = img.resize((TARGET_SIZE, TARGET_SIZE), Image.LANCZOS)

            # Save as PNG for consistency
            if ext != ".png":
                filename = filename.rsplit(".", 1)[0] + ".png"
                storage_path = os.path.join(FAVICON_STORAGE_DIR, filename)

            img.save(storage_path, "PNG", optimize=True)
        except Exception:
            # Fall back to saving raw data
            with open(storage_path, "wb") as f:
                f.write(data)

    _copy_to_site(filename)
    return f"{FAVICON_DB_PREFIX}/{filename}"


def _ext_from_content_type(ct):
    """Map content type to extension."""
    mapping = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/gif": ".gif",
        "image/x-icon": ".ico",
        "image/vnd.microsoft.icon": ".ico",
        "image/svg+xml": ".svg",
        "image/webp": ".webp",
    }
    return mapping.get(ct, ".png")


def _ext_from_url(url):
    """Guess extension from URL."""
    url_lower = url.lower().split("?")[0]
    for ext in EXTENSIONS:
        if url_lower.endswith(ext):
            return ext
    return None


def _fetch_from_google(origin, domain_slug):
    """Strategy 2: Google favicon API."""
    url = f"https://www.google.com/s2/favicons?domain={origin}&sz={FETCH_SIZE}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()

    if len(resp.content) < 100:
        return None

    ct = resp.headers.get("content-type", "")
    ext = _ext_from_content_type(ct)
    filename = f"{domain_slug}-favicon{ext}"
    return _save_favicon(resp.content, filename, ct)


def _extract_favicon_url(soup, origin):
    """Extract best favicon URL from HTML, matching JS priority."""
    # Priority 1: SVG
    el = soup.find("link", rel="icon", type="image/svg+xml")
    if el and el.get("href"):
        return el["href"]

    # Priority 2: PNG (prefer 64x64+)
    png_icons = soup.find_all("link", rel="icon", type="image/png")
    for icon in png_icons:
        sizes = icon.get("sizes", "")
        if "64x64" in sizes or "96x96" in sizes or "128x128" in sizes:
            return icon["href"]
    if png_icons:
        return png_icons[0].get("href")

    # Priority 3: Apple touch icon
    el = soup.find("link", rel="apple-touch-icon")
    if el and el.get("href"):
        return el["href"]

    # Priority 4: Generic icon
    el = soup.find("link", rel="icon")
    if el and el.get("href"):
        return el["href"]

    # Priority 5: Shortcut icon
    el = soup.find("link", rel="shortcut icon")
    if el and el.get("href"):
        return el["href"]

    # Priority 6: Default /favicon.ico
    return origin + "/favicon.ico"


def _resolve_url(href, origin):
    """Convert relative URLs to absolute."""
    if not href:
        return None
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return origin + href
    return origin + "/" + href


def _fetch_from_html(origin, domain_slug):
    """Strategy 3: Extract from page HTML."""
    resp = requests.get(origin, timeout=15, headers={
        "User-Agent": "Mozilla/5.0 (compatible; FaviconFetcher/1.0)"
    })
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    href = _extract_favicon_url(soup, origin)
    favicon_url = _resolve_url(href, origin)
    if not favicon_url:
        return None

    fav_resp = requests.get(favicon_url, timeout=15)
    fav_resp.raise_for_status()

    if len(fav_resp.content) < 50:
        return None

    ext = _ext_from_url(favicon_url) or _ext_from_content_type(
        fav_resp.headers.get("content-type", ""))
    filename = f"{domain_slug}-favicon{ext}"
    return _save_favicon(fav_resp.content, filename)


def fetch_favicon(url):
    """
    Multi-strategy favicon fetching. Returns DB reference path or None.

    Strategies:
    1. Check existing files in storage
    2. Google API
    3. HTML extraction
    """
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        domain = parsed.netloc
        domain_slug = slugify_domain(domain)
    except Exception:
        return None

    # Strategy 1: Check existing
    existing_path, existing_filename = _check_existing(domain_slug)
    if existing_path:
        _copy_to_site(existing_filename)
        return f"{FAVICON_DB_PREFIX}/{existing_filename}"

    # Strategy 2: Google API
    try:
        result = _fetch_from_google(origin, domain_slug)
        if result:
            return result
    except Exception:
        pass

    # Strategy 3: HTML extraction
    try:
        result = _fetch_from_html(origin, domain_slug)
        if result:
            return result
    except Exception:
        pass

    return None
