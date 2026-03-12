import json
import os
import re

BUNDLEDB_PATH = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/bundledb.json"
BLOG_BASE_PATH = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundle.dev/content/blog"


def get_latest_issue_counts(blog_path=None):
    """Derive the next issue number from published blog posts, count items for it."""
    if blog_path is None:
        blog_path = BLOG_BASE_PATH

    # Scan blog directories for highest published issue number
    max_published = 0
    try:
        for year_dir in os.listdir(blog_path):
            year_path = os.path.join(blog_path, year_dir)
            if os.path.isdir(year_path):
                for fname in os.listdir(year_path):
                    m = re.match(r"11ty-bundle-(\d+)\.md$", fname)
                    if m:
                        n = int(m.group(1))
                        if n > max_published:
                            max_published = n
    except OSError:
        pass

    if max_published == 0:
        return None

    next_issue = max_published + 1

    # Count items by type for the next issue in bundledb
    try:
        with open(BUNDLEDB_PATH, "r") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"issue_number": next_issue, "blog_posts": 0, "sites": 0, "releases": 0, "starters": 0}

    counts = {"blog_posts": 0, "sites": 0, "releases": 0, "starters": 0}
    for entry in data:
        if entry.get("Skip"):
            continue
        try:
            if int(entry.get("Issue", 0)) != next_issue:
                continue
        except (ValueError, TypeError):
            continue

        item_type = entry.get("Type", "")
        if item_type == "blog post":
            counts["blog_posts"] += 1
        elif item_type == "site":
            counts["sites"] += 1
        elif item_type == "release":
            counts["releases"] += 1
        elif item_type == "starter":
            counts["starters"] += 1

    return {"issue_number": next_issue, **counts}
