"""Pre-build sync: git sync 11tybundledb and copy missing asset files."""

import json
import os
import re
import shutil
import subprocess

BUNDLEDB_DIR = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb"
BUNDLEDB_PATH = os.path.join(BUNDLEDB_DIR, "bundledb.json")
SHOWCASE_PATH = os.path.join(BUNDLEDB_DIR, "showcase-data.json")

# Source directories (in 11tybundledb)
FAVICON_SOURCE_DIR = os.path.join(BUNDLEDB_DIR, "favicons")
SCREENSHOT_SOURCE_DIR = os.path.join(BUNDLEDB_DIR, "screenshots")

# Destination directories (in 11tybundle.dev)
ELEVENTY_DIR = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundle.dev"
FAVICON_DEST_DIR = os.path.join(ELEVENTY_DIR, "_site", "img", "favicons")
SCREENSHOT_DEST_DIR = os.path.join(ELEVENTY_DIR, "content", "screenshots")


def _run_git(args, cwd=BUNDLEDB_DIR, timeout=30):
    """Run a git command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def sync_bundledb_repo():
    """
    Sync 11tybundledb repo with GitHub.

    Steps:
    1. git add -A
    2. git commit -m "Added new entries" (skip if nothing to commit)
    3. git pull --rebase origin main
    4. git push

    Returns dict with 'success' (bool) and 'message' (str).
    On rebase conflict: abort rebase, return error.
    """
    messages = []

    # Step 1: git add -A
    code, out, err = _run_git(["add", "-A"])
    if code != 0:
        return {"success": False, "message": f"git add failed: {err}"}

    # Step 2: Check if there are changes to commit
    code, status, _ = _run_git(["status", "--porcelain"])
    if status:
        # There are staged changes, commit them
        code, out, err = _run_git(["commit", "-m", "Added new entries"])
        if code != 0:
            return {"success": False, "message": f"git commit failed: {err}"}
        messages.append("Committed local changes")
    else:
        messages.append("No local changes to commit")

    # Step 3: git pull --rebase origin main
    code, out, err = _run_git(["pull", "--rebase", "origin", "main"], timeout=60)
    if code != 0:
        # Check if we're in a rebase conflict
        if "CONFLICT" in err or "conflict" in out.lower():
            # Abort the rebase
            _run_git(["rebase", "--abort"])
            return {
                "success": False,
                "message": f"Rebase conflict detected. Rebase aborted. Please resolve manually.\n{err}",
            }
        return {"success": False, "message": f"git pull --rebase failed: {err}"}

    if "Already up to date" not in out and "Current branch" not in out:
        messages.append("Pulled and rebased remote changes")
    else:
        messages.append("Already up to date with remote")

    # Step 4: git push
    code, out, err = _run_git(["push"], timeout=60)
    if code != 0:
        return {"success": False, "message": f"git push failed: {err}"}
    messages.append("Pushed to remote")

    return {"success": True, "message": "; ".join(messages)}


def _normalize_link(url):
    """Normalize URL for comparison: lowercase, strip trailing slash, add protocol, strip www."""
    s = (url or "").strip().lower().rstrip("/")
    if s and not s.startswith(("http://", "https://")):
        s = "https://" + s
    s = re.sub(r"^(https?://)www\.", r"\1", s)
    return s


def _issue_as_int(val):
    """Convert an Issue field value to int, or return None."""
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _load_bundledb(path=None):
    """Load bundledb.json."""
    with open(path or BUNDLEDB_PATH) as f:
        return json.load(f)


def _load_showcase(path=None):
    """Load showcase-data.json."""
    with open(path or SHOWCASE_PATH) as f:
        return json.load(f)


def load_recent_issue_entries(bundledb_path=None, showcase_path=None):
    """
    Load ALL entries from the latest issue AND the prior issue, INCLUDING starters.

    This ensures assets from both recent issues are checked/copied before build.

    Returns (entries_list, issue_numbers_list) where issue_numbers_list contains
    the issue numbers that were checked (up to 2, in descending order).
    Sites get screenshotpath merged from showcase-data.
    """
    bundledb = _load_bundledb(bundledb_path)
    showcase = _load_showcase(showcase_path)
    showcase_by_link = {_normalize_link(s.get("link", "")): s for s in showcase if s.get("link")}

    # Find all unique issue numbers
    issue_set = set()
    for e in bundledb:
        issue = _issue_as_int(e.get("Issue"))
        if issue is not None:
            issue_set.add(issue)

    if not issue_set:
        return [], []

    # Get the two most recent issues
    sorted_issues = sorted(issue_set, reverse=True)
    target_issues = sorted_issues[:2]  # Latest and prior (if exists)
    target_set = set(target_issues)

    entries = []
    for e in bundledb:
        entry_issue = _issue_as_int(e.get("Issue"))
        if entry_issue not in target_set:
            continue
        if e.get("Skip"):
            continue

        # Merge showcase data for sites
        if e.get("Type") == "site":
            sc = showcase_by_link.get(_normalize_link(e.get("Link", "")))
            if sc:
                e["screenshotpath"] = sc.get("screenshotpath", "")

        entries.append(e)

    return entries, target_issues


def _get_favicon_filename(favicon_path):
    """Extract filename from favicon path (e.g., /img/favicons/foo.png -> foo.png).

    Returns None for SVG icon references (e.g., #icon-globe) which don't need copying.
    """
    if not favicon_path:
        return None
    # Skip SVG icon references (e.g., #icon-globe)
    if favicon_path.startswith("#"):
        return None
    return os.path.basename(favicon_path)


def _get_screenshot_filename(screenshot_path):
    """Extract filename from screenshot path (e.g., /screenshots/foo.jpg -> foo.jpg)."""
    if not screenshot_path:
        return None
    return os.path.basename(screenshot_path)


def check_and_copy_assets(bundledb_path=None, showcase_path=None,
                          favicon_src=None, favicon_dest=None,
                          screenshot_src=None, screenshot_dest=None):
    """
    Check that favicon/screenshot files exist for latest issue entries.
    Copy missing files from 11tybundledb to 11tybundle.dev directories.

    Returns dict with:
    - 'success' (bool)
    - 'message' (str)
    - 'copied' (list of copied file paths)
    - 'missing' (list of missing source files, if any)

    Entry type requirements:
    - blog post: favicon only
    - site: favicon + screenshot
    - starter: favicon + screenshot
    - release: favicon only
    """
    favicon_src_dir = favicon_src or FAVICON_SOURCE_DIR
    favicon_dest_dir = favicon_dest or FAVICON_DEST_DIR
    screenshot_src_dir = screenshot_src or SCREENSHOT_SOURCE_DIR
    screenshot_dest_dir = screenshot_dest or SCREENSHOT_DEST_DIR

    entries, issue_numbers = load_recent_issue_entries(bundledb_path, showcase_path)

    if not entries:
        return {
            "success": True,
            "message": "No entries found for recent issues",
            "copied": [],
            "missing": [],
        }

    copied = []
    missing = []

    # Ensure destination directories exist
    os.makedirs(favicon_dest_dir, exist_ok=True)
    os.makedirs(screenshot_dest_dir, exist_ok=True)

    for entry in entries:
        entry_type = entry.get("Type", "")
        title = entry.get("Title", "Unknown")

        # Check favicon (all types need favicon)
        favicon_path = entry.get("favicon", "")
        if favicon_path:
            filename = _get_favicon_filename(favicon_path)
            if filename:
                src = os.path.join(favicon_src_dir, filename)
                dest = os.path.join(favicon_dest_dir, filename)

                if not os.path.exists(dest):
                    if os.path.exists(src):
                        shutil.copy2(src, dest)
                        copied.append(f"favicon: {filename}")
                    else:
                        missing.append(f"favicon '{filename}' for '{title}' (source not found)")

        # Check screenshot (sites and starters only)
        if entry_type in ("site", "starter"):
            screenshot_path = entry.get("screenshotpath", "")
            if screenshot_path:
                filename = _get_screenshot_filename(screenshot_path)
                if filename:
                    src = os.path.join(screenshot_src_dir, filename)
                    dest = os.path.join(screenshot_dest_dir, filename)

                    if not os.path.exists(dest):
                        if os.path.exists(src):
                            shutil.copy2(src, dest)
                            copied.append(f"screenshot: {filename}")
                        else:
                            missing.append(f"screenshot '{filename}' for '{title}' (source not found)")

    if missing:
        return {
            "success": False,
            "message": f"Missing source files: {'; '.join(missing)}",
            "copied": copied,
            "missing": missing,
        }

    issues_str = " and #".join(str(i) for i in issue_numbers)
    message = f"Checked {len(entries)} entries for issues #{issues_str}"
    if copied:
        message += f"; copied {len(copied)} files"
    else:
        message += "; all assets already in place"

    return {
        "success": True,
        "message": message,
        "copied": copied,
        "missing": [],
    }
