#!/usr/bin/env python3
"""Backfill ogImagePath in showcase-data.json.

Walks every entry, derives ogImagePath from screenshotpath using the
canonical naming convention from scripts/capture-screenshot.js, and writes
the file back with the field added.

Idempotent: entries whose ogImagePath already matches the derived value
are left unchanged. Entries without a screenshotpath get an empty
ogImagePath so the field exists everywhere.

Usage:
  python scripts/backfill-showcase-og-paths.py             # default path
  python scripts/backfill-showcase-og-paths.py <path>      # override path
"""

import json
import os
import sys

# Make services/ importable when run as a script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.og_image import derive_og_image_path

DEFAULT_PATH = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/showcase-data.json"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
    if not os.path.exists(path):
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    with open(path, "r") as f:
        entries = json.load(f)

    added = 0
    updated = 0
    unchanged = 0
    skipped_no_match = 0
    for entry in entries:
        screenshotpath = entry.get("screenshotpath", "")
        derived = derive_og_image_path(screenshotpath)
        existing = entry.get("ogImagePath")

        if existing == derived:
            unchanged += 1
            continue

        if existing is None:
            added += 1
        else:
            updated += 1

        entry["ogImagePath"] = derived

        if screenshotpath and not derived:
            skipped_no_match += 1

    with open(path, "w") as f:
        json.dump(entries, f, indent=2)

    total = len(entries)
    print(f"Processed {total} entries in {path}")
    print(f"  added: {added}")
    print(f"  updated: {updated}")
    print(f"  unchanged: {unchanged}")
    if skipped_no_match:
        print(
            f"  warning: {skipped_no_match} entries have a screenshotpath "
            f"that doesn't match /screenshots/<domain>-large.jpg "
            f"(ogImagePath set to empty)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
