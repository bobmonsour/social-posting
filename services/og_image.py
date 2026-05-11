def derive_og_image_path(screenshotpath):
    """Derive an OG image path from a showcase screenshotpath.

    Mirrors the naming convention in scripts/capture-screenshot.js:
    /screenshots/<domain>-large.jpg -> /og-images/<domain>-og.jpg.
    Returns "" for empty input or paths that don't match the expected shape.
    """
    if not screenshotpath:
        return ""
    if not (screenshotpath.startswith("/screenshots/") and screenshotpath.endswith("-large.jpg")):
        return ""
    return "/og-images/" + screenshotpath[len("/screenshots/"):-len("-large.jpg")] + "-og.jpg"
