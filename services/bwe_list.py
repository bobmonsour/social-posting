import os
import re
from datetime import date

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BWE_FILE = os.path.join(_BASE_DIR, "built-with-eleventy.md")

ALL_PLATFORMS = ["M", "B", "D"]
DEFAULT_PLATFORMS = ["B", "M"]

_LINK_RE = re.compile(r"^\[(.+?)\]\((.+?)\)(?:\s+\{([A-Z,]+)\})?$")
_POSTED_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}) \[(.+?)\]\((.+?)\)(?:\s+\{([A-Z,]+)\})?(?: — (.+))?$"
)


def _parse_platform_spec(spec):
    """Parse a platform specifier like 'M,B,D' into a sorted list."""
    if not spec:
        return []
    return sorted([p.strip() for p in spec.split(",") if p.strip() in ALL_PLATFORMS])


def _extract_platforms_from_status(status):
    """Extract platform letters from legacy status strings like 'Posted to Mastodon, Posted to Bluesky'."""
    if not status:
        return []
    platform_map = {"mastodon": "M", "bluesky": "B", "discord": "D"}
    platforms = []
    for name, letter in platform_map.items():
        if name in status.lower():
            platforms.append(letter)
    return sorted(platforms)


def parse_bwe_file():
    """Parse the BWE markdown file into to_post and posted lists."""
    if not os.path.exists(BWE_FILE):
        return [], []

    with open(BWE_FILE, "r") as f:
        lines = f.read().splitlines()

    to_post = []
    posted = []
    section = None

    for line in lines:
        stripped = line.strip()
        if stripped == "- TO BE POSTED -":
            section = "to_post"
            continue
        elif stripped == "- ALREADY POSTED -":
            section = "posted"
            continue

        if not stripped:
            continue

        if section == "to_post":
            m = _LINK_RE.match(stripped)
            if m:
                platforms = _parse_platform_spec(m.group(3)) or list(DEFAULT_PLATFORMS)
                to_post.append({
                    "name": m.group(1),
                    "url": m.group(2),
                    "platforms": platforms,
                })

        elif section == "posted":
            m = _POSTED_RE.match(stripped)
            if m:
                # Prefer explicit {PLATFORMS} spec, fall back to legacy status parsing
                platform_spec = m.group(4)
                status = m.group(5) or ""
                if platform_spec:
                    platforms = _parse_platform_spec(platform_spec)
                else:
                    platforms = _extract_platforms_from_status(status)
                posted.append({
                    "date": m.group(1),
                    "name": m.group(2),
                    "url": m.group(3),
                    "status": status,
                    "platforms": platforms,
                })

    return to_post, posted


def _write_bwe_file(to_post, posted):
    """Write the BWE markdown file from to_post and posted lists."""
    lines = ["- TO BE POSTED -"]
    for entry in to_post:
        line = f"[{entry['name']}]({entry['url']})"
        platforms = entry.get("platforms", list(DEFAULT_PLATFORMS))
        if sorted(platforms) != sorted(DEFAULT_PLATFORMS):
            line += " {" + ",".join(sorted(platforms)) + "}"
        lines.append(line)
    lines.append("")
    lines.append("- ALREADY POSTED -")
    for entry in posted:
        line = f"{entry['date']} [{entry['name']}]({entry['url']})"
        platforms = entry.get("platforms", [])
        if platforms:
            line += " {" + ",".join(sorted(platforms)) + "}"
        elif entry.get("status"):
            line += f" — {entry['status']}"
        lines.append(line)
    lines.append("")

    with open(BWE_FILE, "w") as f:
        f.write("\n".join(lines))


def get_bwe_lists():
    """Return to_post and posted lists, with formatted dates on posted items."""
    to_post, posted = parse_bwe_file()
    for entry in posted:
        try:
            d = date.fromisoformat(entry["date"])
            entry["date_display"] = d.strftime("%b %-d, %Y")
        except (ValueError, KeyError):
            entry["date_display"] = entry.get("date", "")
    return to_post, posted


def update_bwe_after_post(name, url, posted_platforms, timestamp):
    """Update BWE lists after posting to specific platforms.

    Args:
        name: Site name
        url: Site URL
        posted_platforms: List of platform letters that were successfully posted (e.g. ["M", "B"])
        timestamp: ISO timestamp string
    """
    to_post, posted = parse_bwe_file()
    posted_date = timestamp[:10] if timestamp else date.today().isoformat()

    # Find the to_post entry
    original_platforms = None
    entry_idx = None
    for i, e in enumerate(to_post):
        if e["name"] == name and e["url"] == url:
            original_platforms = e.get("platforms", list(DEFAULT_PLATFORMS))
            entry_idx = i
            break

    if entry_idx is not None:
        remaining = sorted([p for p in original_platforms if p not in posted_platforms])
        if remaining:
            to_post[entry_idx]["platforms"] = remaining
        else:
            to_post.pop(entry_idx)

    # Check if already in posted (previous partial post)
    existing_posted = None
    for e in posted:
        if e["name"] == name and e["url"] == url:
            existing_posted = e
            break

    if existing_posted:
        merged = sorted(set(existing_posted.get("platforms", []) + posted_platforms))
        existing_posted["platforms"] = merged
        existing_posted["date"] = posted_date
        existing_posted["status"] = ""
    else:
        posted.insert(0, {
            "date": posted_date,
            "name": name,
            "url": url,
            "status": "",
            "platforms": sorted(posted_platforms),
        })

    _write_bwe_file(to_post, posted)


def mark_bwe_posted(name, url, timestamp, status_string):
    """Move an entry from TO BE POSTED to ALREADY POSTED with date and status.

    Legacy wrapper — new code should use update_bwe_after_post().
    """
    # Extract platform letters from the status string for the new format
    posted_platforms = _extract_platforms_from_status(status_string)
    if posted_platforms:
        update_bwe_after_post(name, url, posted_platforms, timestamp)
    else:
        # Fallback for unknown status strings: remove from to_post, add to posted
        to_post, posted = parse_bwe_file()
        to_post = [e for e in to_post if not (e["name"] == name and e["url"] == url)]
        posted_date = timestamp[:10] if timestamp else date.today().isoformat()
        posted.insert(0, {
            "date": posted_date,
            "name": name,
            "url": url,
            "status": status_string,
            "platforms": [],
        })
        _write_bwe_file(to_post, posted)


def add_bwe_to_post(title, url):
    """Append a new entry to the TO BE POSTED section."""
    to_post, posted = parse_bwe_file()
    to_post.append({"name": title, "url": url, "platforms": list(DEFAULT_PLATFORMS)})
    _write_bwe_file(to_post, posted)


def delete_bwe_to_post(name, url):
    """Remove an entry from the TO BE POSTED section."""
    to_post, posted = parse_bwe_file()
    to_post = [e for e in to_post if not (e["name"] == name and e["url"] == url)]
    _write_bwe_file(to_post, posted)


def delete_bwe_posted(name, url):
    """Remove an entry from the ALREADY POSTED section."""
    to_post, posted = parse_bwe_file()
    posted = [e for e in posted if not (e["name"] == name and e["url"] == url)]
    _write_bwe_file(to_post, posted)
