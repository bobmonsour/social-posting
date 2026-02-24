"""Bulk content review scanner for showcase-data.json sites.

Run as: python -m services.showcase_review [--test | --full | --site=URL | --report-only]
"""

import argparse
import json
import random
import sys
import time
from datetime import date, datetime
from pathlib import Path

from services.content_review import review_content

_BASE_DIR = Path(__file__).resolve().parent.parent
SHOWCASE_PATH = Path(
    "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/showcase-data.json"
)
ALLOWLIST_PATH = _BASE_DIR / "data" / "showcase-cleared-sites.json"
DEFAULT_RESULTS_PATH = _BASE_DIR / "showcase-review-results.json"
DEFAULT_OUTPUT_PATH = _BASE_DIR / "showcase-review-report.html"


def _normalize_url(url):
    """Normalize a URL for comparison: lowercase, strip trailing slash."""
    return url.strip().lower().rstrip("/")


def load_sites(path=None):
    """Load showcase-data.json, return list of {title, link} dicts."""
    p = path or SHOWCASE_PATH
    with open(p) as f:
        data = json.load(f)
    return [{"title": entry.get("title", ""), "link": entry.get("link", "")} for entry in data if entry.get("link")]


def load_allowlist(path=None):
    """Load cleared-sites JSON if present, return dict keyed by normalized URL."""
    p = Path(path) if path else ALLOWLIST_PATH
    if not p.exists():
        return {}
    with open(p) as f:
        return json.load(f)


def save_allowlist(allowlist, path=None):
    """Write cleared-sites dict to JSON file."""
    p = Path(path) if path else ALLOWLIST_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(allowlist, f, indent=2)
        f.write("\n")


def load_progress(path=None):
    """Load existing results file if present."""
    p = Path(path) if path else DEFAULT_RESULTS_PATH
    if not p.exists():
        return {"reviewed": {}, "started": datetime.now().isoformat(), "last_updated": None}
    with open(p) as f:
        return json.load(f)


def save_progress(data, path=None):
    """Write results dict to JSON file."""
    p = Path(path) if path else DEFAULT_RESULTS_PATH
    data["last_updated"] = datetime.now().isoformat()
    with open(p, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _handle_rate_limit(attempt):
    """Back off on rate limit errors. Returns True if should retry."""
    delays = [30, 60, 120]
    if attempt < len(delays):
        wait = delays[attempt]
        print(f"  Rate limited. Waiting {wait}s before retry (attempt {attempt + 1}/3)...")
        time.sleep(wait)
        return True
    return False


def run_review(delay=2.0, results_path=None, ignore_allowlist=False, limit=None, randomize=False):
    """Main loop: iterate sites, call review_content(), save progress.

    Args:
        delay: Seconds between API calls.
        results_path: Path to progress/results JSON file.
        ignore_allowlist: If True, review all sites regardless of allowlist.
        limit: Max sites to review. None = unlimited, 10 = test mode.
        randomize: If True, randomly select sites to review (used with test mode).
    """
    r_path = Path(results_path) if results_path else DEFAULT_RESULTS_PATH

    sites = load_sites()
    allowlist = {} if ignore_allowlist else load_allowlist()
    progress = load_progress(r_path)
    reviewed_count = 0

    # Build list of eligible sites
    eligible = []
    for site in sites:
        url = _normalize_url(site["link"])
        if url in allowlist and not ignore_allowlist:
            continue
        if url in progress["reviewed"]:
            continue
        eligible.append(site)

    if randomize:
        random.shuffle(eligible)

    total_to_review = len(eligible)
    if limit is not None:
        total_to_review = min(total_to_review, limit)

    print(f"\n{len(sites)} total sites in showcase-data.json")
    print(f"{len(allowlist)} already cleared (allowlist)")
    print(f"{total_to_review} sites to review this run\n")

    if total_to_review == 0:
        print("Nothing to review.")
        return progress

    for site in eligible:
        url = _normalize_url(site["link"])

        if limit is not None and reviewed_count >= limit:
            break

        reviewed_count += 1
        print(f"[{reviewed_count}/{total_to_review}] Reviewing {url}...")

        # Retry logic for rate limits
        result = None
        for attempt in range(4):
            if attempt > 0:
                if not _handle_rate_limit(attempt - 1):
                    break
            result = review_content(site["link"])
            if not (result.get("error") and "rate" in result.get("error", "").lower()):
                break

        progress["reviewed"][url] = {
            "title": site["title"],
            **(result or {"flagged": False, "error": "Max retries exceeded"}),
        }
        save_progress(progress, r_path)

        # Add to permanent allowlist if clean (not flagged, no error)
        if result and not result.get("flagged") and "error" not in result:
            allowlist[url] = {
                "cleared": date.today().isoformat(),
                "title": site["title"],
            }
            save_allowlist(allowlist)

        if result and result.get("flagged"):
            conf = result.get("confidence", "unknown")
            print(f"  FLAGGED ({conf}): {result.get('summary', '')}")
        elif result and "error" in result:
            print(f"  ERROR: {result['error']}")
        else:
            print("  OK")

        # Don't sleep after the last site
        if reviewed_count < total_to_review:
            time.sleep(delay)

    # Generate report at the end
    print(f"\nReview complete. {reviewed_count} sites reviewed.")
    flagged = sum(1 for r in progress["reviewed"].values() if r.get("flagged"))
    errors = sum(1 for r in progress["reviewed"].values() if "error" in r)
    print(f"Flagged: {flagged}, Errors: {errors}")

    return progress


def run_single_site(url):
    """Review a single site and print results. Does not modify allowlist or progress."""
    print(f"Reviewing {url}...")
    result = review_content(url)

    pages = result.get("pages", [])
    pages_desc = ", ".join(pages) if pages else "unknown"
    print(f"Pages checked: {result.get('pages_checked', '?')} ({pages_desc})")
    if result.get("blog_titles_checked"):
        print(f"Blog titles checked: {result['blog_titles_checked']}")

    if result.get("error"):
        print(f"Error: {result['error']}")
    elif result.get("flagged"):
        conf = result.get("confidence", "unknown")
        print(f"Result: FLAGGED (confidence: {conf})")
        print(f"Summary: {result.get('summary', '')}")
    else:
        print("Result: NOT FLAGGED")

    return result


def generate_report(results_path=None, output_path=None):
    """Read results JSON, produce HTML report with only flagged sites."""
    r_path = Path(results_path) if results_path else DEFAULT_RESULTS_PATH
    o_path = Path(output_path) if output_path else DEFAULT_OUTPUT_PATH

    if not r_path.exists():
        print(f"No results file found at {r_path}")
        return

    with open(r_path) as f:
        data = json.load(f)

    reviewed = data.get("reviewed", {})
    flagged_entries = []
    error_count = 0
    for url, result in reviewed.items():
        if result.get("flagged"):
            flagged_entries.append({"url": url, **result})
        if "error" in result:
            error_count += 1

    # Sort by confidence: high -> medium -> low
    confidence_order = {"high": 0, "medium": 1, "low": 2}
    flagged_entries.sort(key=lambda e: confidence_order.get(e.get("confidence", "low"), 3))

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Build HTML
    rows = []
    for entry in flagged_entries:
        conf = entry.get("confidence", "unknown")
        conf_colors = {"high": "#dc3545", "medium": "#fd7e14", "low": "#ffc107"}
        conf_color = conf_colors.get(conf, "#6c757d")

        pages_html = ""
        for page in entry.get("pages", []):
            pages_html += f'<li><a href="{page}">{page}</a></li>'

        blog_titles = entry.get("blog_titles_checked")
        blog_note = f"<p><em>{blog_titles} blog titles also checked</em></p>" if blog_titles else ""

        rows.append(f"""
        <div class="entry">
            <h3><a href="{entry['url']}">{entry.get('title', entry['url'])}</a></h3>
            <span class="confidence" style="background:{conf_color}">{conf}</span>
            <p class="summary">{entry.get('summary', '')}</p>
            <details>
                <summary>Pages checked ({len(entry.get('pages', []))})</summary>
                <ul>{pages_html}</ul>
                {blog_note}
            </details>
        </div>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Showcase Content Review Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #333; }}
  h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.5rem; }}
  .stats {{ background: #f8f9fa; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
  .stats span {{ margin-right: 2rem; }}
  .entry {{ border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin: 1rem 0; }}
  .entry h3 {{ margin-top: 0; }}
  .entry h3 a {{ color: #0969da; text-decoration: none; }}
  .entry h3 a:hover {{ text-decoration: underline; }}
  .confidence {{ display: inline-block; color: #fff; padding: 2px 8px; border-radius: 4px;
                 font-size: 0.85em; font-weight: bold; text-transform: uppercase; }}
  .summary {{ margin: 0.5rem 0; }}
  details {{ margin-top: 0.5rem; }}
  details ul {{ margin: 0.5rem 0; padding-left: 1.5rem; }}
  details li {{ word-break: break-all; }}
  .none {{ color: #6c757d; font-style: italic; }}
</style>
</head>
<body>
<h1>Showcase Content Review Report</h1>
<div class="stats">
  <span><strong>Generated:</strong> {now}</span>
  <span><strong>Sites reviewed:</strong> {len(reviewed)}</span>
  <span><strong>Flagged:</strong> {len(flagged_entries)}</span>
  <span><strong>Errors:</strong> {error_count}</span>
</div>
{"".join(rows) if rows else '<p class="none">No flagged sites found.</p>'}
</body>
</html>"""

    with open(o_path, "w") as f:
        f.write(html)

    print(f"Report written to {o_path}")
    print(f"  {len(reviewed)} sites reviewed, {len(flagged_entries)} flagged, {error_count} errors")


def main():
    parser = argparse.ArgumentParser(description="Showcase Content Review Scanner")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--test", action="store_true", help="Review 10 randomly selected non-allowlisted sites")
    mode_group.add_argument("--full", action="store_true", help="Review all remaining sites")
    mode_group.add_argument("--site", type=str, help="Review a single URL (ad-hoc, not saved)")
    mode_group.add_argument("--report-only", action="store_true", help="Generate report from existing results")

    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between API calls (default: 2.0)")
    parser.add_argument("--ignore-allowlist", action="store_true", help="Review all sites, ignoring allowlist")
    parser.add_argument("--results", type=str, default=None, help="Path to results JSON file")
    parser.add_argument("--output", type=str, default=None, help="Path to HTML report output")

    args = parser.parse_args()

    if args.report_only:
        generate_report(args.results, args.output)
        return

    if args.site:
        run_single_site(args.site)
        return

    if args.test:
        limit = 10
        randomize = True
    elif args.full:
        limit = None
        randomize = False
    else:
        # Interactive prompt
        sites = load_sites()
        allowlist = load_allowlist()
        progress = load_progress(args.results)

        to_review = sum(
            1 for s in sites
            if _normalize_url(s["link"]) not in allowlist
            and _normalize_url(s["link"]) not in progress.get("reviewed", {})
        )

        print("Showcase Content Review")
        print("=======================")
        print(f"{len(sites)} sites in showcase-data.json")
        print(f"{len(allowlist)} already cleared (allowlist)")
        print(f"{to_review} sites to review")
        print()
        print("Run mode:")
        print("  [T] Test run - review 10 randomly selected sites")
        print("  [F] Full run - review all remaining sites")
        print()

        choice = input("Choose [T/F]: ").strip().upper()
        if choice == "T":
            limit = 10
            randomize = True
        elif choice == "F":
            limit = None
            randomize = False
        else:
            print("Invalid choice. Exiting.")
            sys.exit(1)

    progress = run_review(
        delay=args.delay,
        results_path=args.results,
        ignore_allowlist=args.ignore_allowlist,
        limit=limit,
        randomize=randomize,
    )
    generate_report(args.results, args.output)


if __name__ == "__main__":
    main()
