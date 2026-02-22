"""Generate issue records from bundledb.json.

Ported from dbtools/lib/genissuerecords.js — pure JSON-in/JSON-out with no
Node dependencies.
"""

import json
import os


def generate_issue_records(bundledb_path, output_path):
    """Read bundledb.json, build per-issue counts, and write issuerecords.json.

    Skips entries with ``Skip: true``.  Fills gaps so every issue number from 1
    to the maximum has a record (with zero counts for missing issues).

    Returns the list of issue-record dicts that was written.
    """
    with open(bundledb_path, "r", encoding="utf-8") as f:
        bundle_records = json.load(f)

    counts_by_issue: dict[int, dict[str, int]] = {}

    for item in bundle_records:
        if item.get("Skip"):
            continue

        try:
            issue_num = int(item.get("Issue", 0))
        except (TypeError, ValueError):
            continue
        if issue_num < 1:
            continue

        if issue_num not in counts_by_issue:
            counts_by_issue[issue_num] = {"blogPosts": 0, "releases": 0, "sites": 0}
        bucket = counts_by_issue[issue_num]

        entry_type = item.get("Type")
        if entry_type == "blog post":
            bucket["blogPosts"] += 1
        elif entry_type == "release":
            bucket["releases"] += 1
        elif entry_type == "site":
            bucket["sites"] += 1

    max_issue = max(counts_by_issue.keys()) if counts_by_issue else 0

    issue_records = []
    for i in range(1, max_issue + 1):
        c = counts_by_issue.get(i, {"blogPosts": 0, "releases": 0, "sites": 0})
        issue_records.append({
            "issue": i,
            "blogPosts": c["blogPosts"],
            "releases": c["releases"],
            "sites": c["sites"],
        })

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(issue_records, f, indent=2)

    return issue_records
