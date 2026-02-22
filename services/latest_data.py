"""Generate latest-issue filtered data files.

Ported from dbtools/generate-latest-data.js — pure JSON-in/JSON-out with no
Node dependencies.
"""

import json
import os
from datetime import datetime


def _parse_date_naive(date_str):
    """Parse an ISO date string and return a naive datetime (tz stripped).

    The JS version uses ``new Date(str)`` which compares timestamps regardless
    of timezone notation.  We mirror that by always stripping tz info.
    Returns None if parsing fails.
    """
    # Handle 'Z' suffix that fromisoformat doesn't accept in Python <3.11
    s = date_str.replace("Z", "+00:00") if date_str.endswith("Z") else date_str
    try:
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


def generate_latest_data(bundledb_path, showcase_path,
                         bundledb_output_path, showcase_output_path):
    """Filter bundledb and showcase data to the latest issue and write output files.

    Steps (mirroring the JS version):
    1. Find the maximum issue number across all bundledb entries.
    2. Filter bundledb entries matching that issue number.
    3. Find the earliest date among those entries.
    4. Filter showcase entries whose date >= that earliest date.
    5. Write both filtered lists to their output paths.

    Returns a dict with keys: latest_issue, bundledb_count, showcase_count.
    """
    with open(bundledb_path, "r", encoding="utf-8") as f:
        bundle_data = json.load(f)

    # Find latest issue number
    max_issue = 0
    for entry in bundle_data:
        issue = entry.get("Issue")
        if issue is not None:
            try:
                issue_num = int(issue)
                if issue_num > max_issue:
                    max_issue = issue_num
            except (TypeError, ValueError):
                pass

    if max_issue == 0:
        raise ValueError("No valid issue numbers found in bundledb.json")

    # Filter entries for latest issue
    latest_entries = []
    for entry in bundle_data:
        try:
            if int(entry.get("Issue", 0)) == max_issue:
                latest_entries.append(entry)
        except (TypeError, ValueError):
            pass

    if not latest_entries:
        raise ValueError(f"No entries found for issue #{max_issue}")

    # Write bundledb-latest-issue.json
    os.makedirs(os.path.dirname(bundledb_output_path) or ".", exist_ok=True)
    with open(bundledb_output_path, "w", encoding="utf-8") as f:
        json.dump(latest_entries, f, indent=2)

    # Find earliest date among latest-issue entries
    earliest_date = None
    for entry in latest_entries:
        date_str = entry.get("Date")
        if date_str:
            entry_date = _parse_date_naive(date_str)
            if entry_date is not None:
                if earliest_date is None or entry_date < earliest_date:
                    earliest_date = entry_date

    if earliest_date is None:
        raise ValueError("No valid dates found in latest issue entries")

    # Read and filter showcase data
    with open(showcase_path, "r", encoding="utf-8") as f:
        showcase_data = json.load(f)

    filtered_showcase = []
    for entry in showcase_data:
        date_str = entry.get("date")
        if not date_str:
            continue
        entry_date = _parse_date_naive(date_str)
        if entry_date is None:
            continue
        if entry_date >= earliest_date:
            filtered_showcase.append(entry)

    # Write showcase-data-latest-issue.json
    os.makedirs(os.path.dirname(showcase_output_path) or ".", exist_ok=True)
    with open(showcase_output_path, "w", encoding="utf-8") as f:
        json.dump(filtered_showcase, f, indent=2)

    return {
        "latest_issue": max_issue,
        "bundledb_count": len(latest_entries),
        "showcase_count": len(filtered_showcase),
    }
