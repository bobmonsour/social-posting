import os
import re
from datetime import date

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BWE_FILE = os.path.join(_BASE_DIR, "built-with-eleventy.md")

_LINK_RE = re.compile(r"^\[(.+?)\]\((.+?)\)$")
_POSTED_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}) \[(.+?)\]\((.+?)\)(?: — (.+))?$"
)


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
                to_post.append({"name": m.group(1), "url": m.group(2)})

        elif section == "posted":
            m = _POSTED_RE.match(stripped)
            if m:
                posted.append({
                    "date": m.group(1),
                    "name": m.group(2),
                    "url": m.group(3),
                    "status": m.group(4) or "",
                })

    return to_post, posted


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


def mark_bwe_posted(name, url, timestamp, status_string):
    """Move an entry from TO BE POSTED to ALREADY POSTED with date and status."""
    to_post, posted = parse_bwe_file()

    # Remove from to_post
    to_post = [e for e in to_post if not (e["name"] == name and e["url"] == url)]

    # Add to front of posted
    posted_date = timestamp[:10] if timestamp else date.today().isoformat()
    posted_entry = {
        "date": posted_date,
        "name": name,
        "url": url,
        "status": status_string,
    }
    posted.insert(0, posted_entry)

    # Rewrite the file
    lines = ["- TO BE POSTED -"]
    for entry in to_post:
        lines.append(f"[{entry['name']}]({entry['url']})")
    lines.append("")
    lines.append("- ALREADY POSTED -")
    for entry in posted:
        line = f"{entry['date']} [{entry['name']}]({entry['url']})"
        if entry.get("status"):
            line += f" — {entry['status']}"
        lines.append(line)
    lines.append("")

    with open(BWE_FILE, "w") as f:
        f.write("\n".join(lines))


def delete_bwe_posted(name, url):
    """Remove an entry from the ALREADY POSTED section."""
    to_post, posted = parse_bwe_file()
    posted = [e for e in posted if not (e["name"] == name and e["url"] == url)]

    lines = ["- TO BE POSTED -"]
    for entry in to_post:
        lines.append(f"[{entry['name']}]({entry['url']})")
    lines.append("")
    lines.append("- ALREADY POSTED -")
    for entry in posted:
        line = f"{entry['date']} [{entry['name']}]({entry['url']})"
        if entry.get("status"):
            line += f" — {entry['status']}"
        lines.append(line)
    lines.append("")

    with open(BWE_FILE, "w") as f:
        f.write("\n".join(lines))
