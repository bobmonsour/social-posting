"""Remove a site's generated Showcase page from the 11tybundle.dev build output.

Eleventy never prunes ``_site``, so a Showcase page whose entry has been deleted
from ``showcase-data.json`` survives the next build and gets shipped by
``wrangler deploy``. Deleting the entry in the editor calls in here to remove the
stale directory too.
"""

import shutil
from pathlib import Path
from urllib.parse import urlparse

from services.slugify import slugify

SHOWCASE_OUTPUT_DIR = Path(
    "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundle.dev/_site/showcase"
)


def showcase_slug_for_site(site_url):
    """Return the Showcase page slug for *site_url*, or None if it has none.

    Mirrors the Eleventy permalink in 11tybundle.dev's
    ``content/showcase/sites.njk``: ``/showcase/{{ site.link | getHostname | slugify }}/``
    where ``getHostname`` is ``new URL(link).hostname`` and ``slugify`` matches
    ``@sindresorhus/slugify`` (our ``services.slugify``).
    """
    try:
        hostname = urlparse(site_url).hostname
    except ValueError:
        return None
    if not hostname:
        return None
    return slugify(hostname) or None


def showcase_output_path(site_url):
    """Return the ``_site/showcase/<slug>/`` Path for *site_url*, or None.

    The directory need not exist. Returns None when *site_url* has no usable
    slug, or -- belt and braces, since a hostname slug cannot contain a
    separator -- when the result would escape the showcase directory.
    """
    slug = showcase_slug_for_site(site_url)
    if not slug:
        return None
    target = SHOWCASE_OUTPUT_DIR / slug
    if target.parent != SHOWCASE_OUTPUT_DIR or target == SHOWCASE_OUTPUT_DIR:
        return None
    return target


def delete_showcase_output(site_url):
    """Delete ``_site/showcase/<slug>/`` for *site_url*.

    Best effort: never raises, so a failure here cannot break the entry delete.
    Returns a dict with ``status`` (``deleted``, ``not_found``, ``invalid``, or
    ``error``), ``slug``, and ``path``.
    """
    target = showcase_output_path(site_url)
    if target is None:
        return {"status": "invalid", "slug": showcase_slug_for_site(site_url), "path": None}

    slug = target.name

    if not target.is_dir():
        return {"status": "not_found", "slug": slug, "path": str(target)}

    try:
        shutil.rmtree(target)
    except OSError as e:
        return {"status": "error", "slug": slug, "path": str(target), "error": str(e)}

    return {"status": "deleted", "slug": slug, "path": str(target)}
