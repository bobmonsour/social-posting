import json

BUNDLEDB_PATH = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/bundledb.json"


def get_latest_issue_counts():
    """Read bundledb.json and return the latest issue number with item counts."""
    try:
        with open(BUNDLEDB_PATH, "r") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    # Find the highest issue number
    issue_numbers = []
    for entry in data:
        try:
            issue_numbers.append(int(entry.get("Issue", 0)))
        except (ValueError, TypeError):
            continue

    if not issue_numbers:
        return None

    latest = max(issue_numbers)

    # Count items by type for the latest issue, skipping entries with Skip
    counts = {"blog_posts": 0, "sites": 0, "releases": 0, "starters": 0}
    for entry in data:
        if entry.get("Skip"):
            continue
        try:
            if int(entry.get("Issue", 0)) != latest:
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

    return {"issue_number": latest, **counts}
