"""Verify that recently added 11ty Bundle entries rendered correctly in the build output."""

import json
import sys
from pathlib import Path

from bs4 import BeautifulSoup

SITE_DIR = Path("/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundle.dev/_site")
BUNDLEDB_PATH = Path(
    "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/bundledb.json"
)
SHOWCASE_PATH = Path(
    "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/showcase-data.json"
)

# Home page shows exactly 11 entries per section
HOME_PAGE_LIMIT = 11

# Section headings on the home page, keyed by entry type.
# Starters are excluded — they sort by GitHub modification date (fetched at
# build time), not by the date stored in bundledb.
SECTION_HEADINGS = {
    "blog post": "From the firehose",
    "site": "Recent sites",
    "release": "Recent releases",
}


def _issue_as_int(val):
    """Convert an Issue field value to int, or return None."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _load_bundledb():
    with open(BUNDLEDB_PATH) as f:
        return json.load(f)


def _load_showcase():
    with open(SHOWCASE_PATH) as f:
        return json.load(f)


def load_entries_by_date(target_date):
    """Load entries matching a target date (YYYY-MM-DD)."""
    bundledb = _load_bundledb()
    return [
        e
        for e in bundledb
        if e.get("Date", "").startswith(target_date)
        and e.get("Type") != "starter"
        and not e.get("Skip")
    ]


def load_entries_by_latest_issue():
    """Load entries with the highest issue number in bundledb."""
    bundledb = _load_bundledb()
    issues = []
    for e in bundledb:
        issue = e.get("Issue")
        if issue is not None:
            try:
                issues.append(int(issue))
            except (ValueError, TypeError):
                pass
    if not issues:
        return [], 0
    max_issue = max(issues)
    db_entries = [
        e
        for e in bundledb
        if _issue_as_int(e.get("Issue")) == max_issue
        and e.get("Type") != "starter"
        and not e.get("Skip")
    ]
    return db_entries, max_issue


def _find_section(soup, heading_text):
    """Find the parent element of an h2 containing heading_text."""
    for h2 in soup.find_all("h2"):
        if heading_text in h2.get_text():
            return h2.parent
    return None


def _file_exists(src):
    """Check if a src path (e.g. /img/favicons/foo.png) exists in _site."""
    if not src:
        return False
    rel = src.lstrip("/")
    return (SITE_DIR / rel).exists()


def _check_entry_in_list(li, title):
    """Check a feeds__item li for a matching title. Returns result dict or None."""
    a = li.find("a")
    if not a:
        return None
    li_title = a.get_text(strip=True)
    if title not in li_title and li_title not in title:
        return None

    # Check favicon - could be <img> or <svg>
    img = li.find("img", class_="favicon")
    svg = li.find("svg", class_="favicon")

    if img:
        src = img.get("src", "")
        favicon_ok = _file_exists(src)
        favicon_src = src
    elif svg:
        favicon_ok = True
        favicon_src = "inline SVG"
    else:
        favicon_ok = False
        favicon_src = None

    return {"favicon_ok": favicon_ok, "favicon_src": favicon_src}


def _check_entry_in_directory(card, title):
    """Check a directory__card div for a matching title. Returns result dict or None."""
    h3 = card.find("h3")
    if not h3:
        return None
    a = h3.find("a")
    if not a:
        return None
    card_title = a.get_text(strip=True)
    if title not in card_title and card_title not in title:
        return None

    img = card.find("img", class_="favicon")
    svg = card.find("svg", class_="favicon")
    if img:
        src = img.get("src", "")
        return {"favicon_ok": _file_exists(src), "favicon_src": src}
    elif svg:
        return {"favicon_ok": True, "favicon_src": "inline SVG"}
    return {"favicon_ok": False, "favicon_src": None}


def verify_home_page(entries):
    """Verify entries appear on the home page (up to 11 per section)."""
    index_path = SITE_DIR / "index.html"
    if not index_path.exists():
        return [], []
    with open(index_path) as f:
        soup = BeautifulSoup(f, "html.parser")

    results = []
    overflow = []  # entries beyond the 11-item home page limit

    by_type = {}
    for entry in entries:
        by_type.setdefault(entry["Type"], []).append(entry)

    for entry_type, type_entries in by_type.items():
        heading = SECTION_HEADINGS.get(entry_type)
        if not heading:
            for entry in type_entries:
                results.append(
                    {
                        "section": "Home Page",
                        "title": entry["Title"],
                        "link": entry.get("Link", ""),
                        "type": entry_type,
                        "passed": False,
                        "error": f"Unknown type: {entry_type}",
                    }
                )
            continue

        section = _find_section(soup, heading)
        if not section:
            for entry in type_entries:
                results.append(
                    {
                        "section": f"Home Page — {heading}",
                        "title": entry["Title"],
                        "link": entry.get("Link", ""),
                        "type": entry_type,
                        "passed": False,
                        "error": "Section not found in HTML",
                    }
                )
            continue

        # Build ordered list of entries in the section
        items = section.find_all("li", class_="feeds__item")
        section_titles = []
        section_items = {}
        for li in items:
            a = li.find("a")
            if a:
                t = a.get_text(strip=True)
                section_titles.append(t)
                section_items[t] = li

        for entry in type_entries:
            title = entry["Title"]

            # Try to find in home page section
            matched_title = None
            position = None
            for i, st in enumerate(section_titles):
                if title in st or st in title:
                    matched_title = st
                    position = i + 1
                    break

            if matched_title is None:
                # Not on home page — this is expected overflow if there are
                # more entries than HOME_PAGE_LIMIT
                overflow.append(entry)
                continue

            li = section_items[matched_title]
            check = _check_entry_in_list(li, title)

            result = {
                "section": f"Home Page — {heading}",
                "title": title,
                "link": entry.get("Link", ""),
                "type": entry_type,
                "position": position,
                "favicon_ok": check["favicon_ok"] if check else False,
                "favicon_src": check["favicon_src"] if check else None,
                "passed": check["favicon_ok"] if check else False,
            }
            if not result["passed"]:
                result["error"] = (
                    f"favicon missing — src: {result['favicon_src'] or 'none'}"
                )
            results.append(result)

    return results, overflow


def _load_firehose_cards():
    """Load directory cards from the main firehose page and all year pages."""
    cards = []
    firehose_dir = SITE_DIR / "firehose"
    if not firehose_dir.exists():
        return cards
    # Main page + year subpages (e.g., firehose/2025/index.html)
    pages = [firehose_dir / "index.html"]
    for child in firehose_dir.iterdir():
        if child.is_dir():
            year_page = child / "index.html"
            if year_page.exists():
                pages.append(year_page)
    for page in pages:
        with open(page) as f:
            soup = BeautifulSoup(f, "html.parser")
        cards.extend(soup.find_all("div", class_="directory__card"))
    return cards


def verify_firehose(entries):
    """Verify blog post entries on the firehose pages."""
    blog_entries = [e for e in entries if e["Type"] == "blog post"]
    if not blog_entries:
        return []

    firehose_path = SITE_DIR / "firehose" / "index.html"
    if not firehose_path.exists():
        return [
            {
                "title": "N/A",
                "passed": False,
                "error": "_site/firehose/index.html missing",
            }
        ]

    cards = _load_firehose_cards()

    results = []
    for entry in blog_entries:
        title = entry["Title"]
        result = {
            "section": "Firehose page",
            "title": title,
            "link": entry.get("Link", ""),
            "type": "blog post",
            "favicon_ok": None,
            "favicon_src": None,
            "passed": False,
        }

        matched = None
        for card in cards:
            matched = _check_entry_in_directory(card, title)
            if matched:
                break

        if not matched:
            result["error"] = "NOT FOUND on firehose page"
        else:
            result["favicon_ok"] = matched["favicon_ok"]
            result["favicon_src"] = matched["favicon_src"]
            result["passed"] = matched["favicon_ok"]
            if not result["passed"]:
                result["error"] = (
                    f"favicon missing — src: {matched['favicon_src'] or 'none'}"
                )

        results.append(result)

    return results


def verify_showcase(entries):
    """Verify site entries appear on the showcase page with valid images."""
    showcase_path = SITE_DIR / "showcase" / "index.html"
    if not showcase_path.exists():
        return [
            {
                "title": "N/A",
                "passed": False,
                "error": "_site/showcase/index.html missing",
            }
        ]

    site_entries = [e for e in entries if e["Type"] == "site"]
    if not site_entries:
        return []

    with open(showcase_path) as f:
        soup = BeautifulSoup(f, "html.parser")

    cards = soup.find_all("figure", class_="showcase__card")

    results = []
    for entry in site_entries:
        title = entry["Title"]
        link = entry["Link"]
        result = {
            "section": "Showcase page",
            "title": title,
            "link": link,
            "type": "site",
            "favicon_ok": None,
            "favicon_src": None,
            "screenshot_ok": None,
            "screenshot_src": None,
            "passed": False,
        }

        matched_card = None
        for card in cards:
            figcaption = card.find("figcaption")
            if not figcaption:
                continue
            a = figcaption.find("a")
            if a:
                link_text = a.get_text(strip=True)
                if link.rstrip("/") in link_text.rstrip("/") or link_text.rstrip(
                    "/"
                ) in link.rstrip("/"):
                    matched_card = card
                    break

        if matched_card is None:
            result["error"] = "NOT FOUND on showcase page"
            results.append(result)
            continue

        # Check favicon in figcaption — could be <img> or <svg> (icon fallback)
        figcaption = matched_card.find("figcaption")
        favicon_img = figcaption.find("img", class_="favicon") if figcaption else None
        favicon_svg = figcaption.find("svg", class_="favicon") if figcaption else None
        if favicon_img:
            src = favicon_img.get("src", "")
            result["favicon_src"] = src
            result["favicon_ok"] = _file_exists(src)
        elif favicon_svg:
            result["favicon_src"] = "inline SVG"
            result["favicon_ok"] = True
        else:
            result["favicon_ok"] = False

        # Check screenshot image (the <img> inside <picture>)
        picture = matched_card.find("picture")
        if picture:
            screenshot_img = picture.find("img")
            if screenshot_img:
                src = screenshot_img.get("src", "")
                result["screenshot_src"] = src
                result["screenshot_ok"] = _file_exists(src)
            else:
                result["screenshot_ok"] = False
        else:
            result["screenshot_ok"] = False

        result["passed"] = result["favicon_ok"] and result["screenshot_ok"]
        if not result["passed"]:
            errors = []
            if not result["favicon_ok"]:
                errors.append(
                    f"favicon missing — src: {result['favicon_src'] or 'none'}"
                )
            if not result["screenshot_ok"]:
                errors.append(
                    f"screenshot missing — src: {result['screenshot_src'] or 'none'}"
                )
            result["error"] = "; ".join(errors)

        results.append(result)

    return results


def format_report(all_results, label=""):
    """Format the verification report."""
    passed = sum(1 for r in all_results if r["passed"])
    total = len(all_results)

    lines = []
    status = "PASSED" if passed == total else "FAILED"
    header = f"Verification {status} ({passed}/{total} checks)"
    if label:
        header += f" — {label}"
    lines.append(header)

    # On success, no further detail needed
    failures = [r for r in all_results if not r["passed"]]
    if not failures:
        return "\n".join(lines)

    lines.append("")

    # Group failures by entry type
    TYPE_LABELS = {
        "blog post": "Blog post failures",
        "site": "Site failures",
        "release": "Release failures",
    }
    by_type = {}
    for r in failures:
        by_type.setdefault(r.get("type", "unknown"), []).append(r)

    for entry_type, type_failures in by_type.items():
        lines.append(f"{TYPE_LABELS.get(entry_type, entry_type + ' failures')}:")
        for r in type_failures:
            lines.append(f'  {r["title"]} — {r.get("link", "")}')
        lines.append("")

    return "\n".join(lines)


def _run_verification(entries, label=""):
    """Core verification logic shared by date and issue modes."""
    if not entries:
        return f"No entries found{' for ' + label if label else ''}.", True

    # Check home page (up to 11 per section); overflow entries go to subpages
    home_results, overflow = verify_home_page(entries)

    # Overflow blog posts get checked on the firehose page
    overflow_blog = [e for e in overflow if e["Type"] == "blog post"]
    firehose_results = verify_firehose(overflow_blog) if overflow_blog else []

    # All site entries get checked on the showcase page (not just overflow)
    showcase_results = verify_showcase(entries)

    all_results = home_results + firehose_results + showcase_results
    report = format_report(all_results, label=label)
    success = all(r["passed"] for r in all_results)

    return report, success


def verify_by_date(target_date):
    """Run verification for entries matching a date. Returns (report_str, success_bool)."""
    entries = load_entries_by_date(target_date)
    return _run_verification(entries, label=target_date)


def verify_latest_issue():
    """Run verification for entries with the latest issue number. Returns (report_str, success_bool)."""
    entries, issue_num = load_entries_by_latest_issue()
    return _run_verification(entries, label=f"Issue #{issue_num}")


# Default entry point — uses latest issue
verify = verify_latest_issue


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        report, success = verify_by_date(sys.argv[1])
    else:
        report, success = verify_latest_issue()
    print(report)
    sys.exit(0 if success else 1)
