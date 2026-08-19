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
OG_IMAGE_SOURCE_DIR = os.path.join(BUNDLEDB_DIR, "og-images")
OG_IMAGE_DEST_DIR = os.path.join(ELEVENTY_DIR, "content", "og-images")

# Destination mtimes come from shutil.copy2, so they should match the source
# exactly; allow a second of slack for filesystem timestamp resolution.
MTIME_TOLERANCE_SECONDS = 1


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


def _ahead_count():
    """Commits on HEAD that have not reached the upstream branch.

    Returns 0 when the branch is in sync, and also when there is no upstream to
    compare against -- without one there is nothing meaningful to report.
    """
    code, out, _ = _run_git(["rev-list", "--count", "@{u}..HEAD"])
    if code != 0:
        return 0
    try:
        return int(out.strip())
    except ValueError:
        return 0


def sync_bundledb_repo(commit_message="Added new entries"):
    """
    Sync the 11tybundledb repo with GitHub.

    The single helper for this repo, shared by /editor/prebuild-sync,
    /editor/deploy, and /editor/verify-site. Each caller passes its own commit
    message so the log says which flow produced a commit.

    Steps:
    1. git add -A
    2. git commit (skip if nothing to commit)
    3. git pull --rebase origin main
    4. git push

    The push is unconditional, so commits already sitting in the local repo
    reach origin whether or not this run created any.

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
        code, out, err = _run_git(["commit", "-m", commit_message])
        if code != 0:
            return {"success": False, "message": f"git commit failed: {err}"}
        messages.append("Committed local changes")
    else:
        ahead = _ahead_count()
        if ahead:
            messages.append(f"No local changes to commit, {ahead} previously committed to push")
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
                e["ogImagePath"] = sc.get("ogImagePath", "")

        entries.append(e)

    return entries, target_issues


def _asset_filename(asset_path):
    """Extract the filename from an asset path (e.g. /img/favicons/foo.png -> foo.png).

    Returns None when there is no file to copy: an empty value, or an SVG icon
    reference such as #icon-globe.
    """
    if not asset_path or asset_path.startswith("#"):
        return None
    return os.path.basename(asset_path)


def collect_asset_refs(bundledb_path=None, showcase_path=None):
    """
    Collect every asset reference in the full DB, de-duped by (kind, filename).

    bundledb.json supplies favicon refs for all types plus screenshot refs for
    starters, which carry their own screenshotpath. showcase-data.json supplies
    favicon, screenshot, and og-image refs for the full site list, which is far
    larger than bundledb's site entries. Entries flagged Skip/skip never render,
    so their assets are not required.

    Returns a dict of (kind, filename) -> title of the first entry referencing it.
    """
    refs = {}

    def add(kind, asset_path, title):
        filename = _asset_filename(asset_path)
        if filename:
            refs.setdefault((kind, filename), title or "Unknown")

    for entry in _load_bundledb(bundledb_path):
        if entry.get("Skip"):
            continue
        title = entry.get("Title")
        add("favicon", entry.get("favicon"), title)
        add("screenshot", entry.get("screenshotpath"), title)

    for site in _load_showcase(showcase_path):
        if site.get("skip"):
            continue
        title = site.get("title")
        add("favicon", site.get("favicon"), title)
        add("screenshot", site.get("screenshotpath"), title)
        add("og-image", site.get("ogImagePath"), title)

    return refs


def _recent_asset_refs(bundledb_path=None, showcase_path=None):
    """
    The (kind, filename) refs belonging to the recent-issue window.

    A missing source file for one of these blocks the build; anything older is
    reported as a warning so historical rot cannot hold every build hostage.

    Returns (refs_set, issue_numbers).
    """
    entries, issue_numbers = load_recent_issue_entries(bundledb_path, showcase_path)

    recent = set()
    for entry in entries:
        for kind, asset_path in (
            ("favicon", entry.get("favicon")),
            ("screenshot", entry.get("screenshotpath")),
            ("og-image", entry.get("ogImagePath")),
        ):
            filename = _asset_filename(asset_path)
            if filename:
                recent.add((kind, filename))

    return recent, issue_numbers


def _copy_state(src, dest):
    """
    Decide what the destination needs.

    Returns "copied" when dest is absent, "refreshed" when it is present but
    stale, or None when it already matches the source.

    Staleness is an rsync-style quick check on size, then mtime. The mtime
    comparison is deliberately one-directional: only a source NEWER than the
    destination means the source was replaced after the copy. A destination
    newer than its source is not stale -- capture-screenshot.js writes
    content/screenshots and 11tybundledb in the same run rather than copying
    between them, leaving ~1,300 byte-identical screenshots whose destinations
    are newer. Comparing mtimes symmetrically would recopy all of them on every
    build, forever.
    """
    try:
        dest_stat = os.stat(dest)
    except FileNotFoundError:
        return "copied"

    src_stat = os.stat(src)
    if dest_stat.st_size != src_stat.st_size:
        return "refreshed"
    if src_stat.st_mtime - dest_stat.st_mtime > MTIME_TOLERANCE_SECONDS:
        return "refreshed"
    return None


def check_and_copy_assets(bundledb_path=None, showcase_path=None,
                          favicon_src=None, favicon_dest=None,
                          screenshot_src=None, screenshot_dest=None,
                          og_src=None, og_dest=None):
    """
    Reconcile every favicon, screenshot, and og-image referenced by the DB
    against the 11tybundle.dev directories, copying what is missing or stale.

    The destination directories are all gitignored local copies, so they drift
    silently; only 11tybundledb is the git-backed source of truth. Reconciling
    the full DB rather than the recent issue is a few thousand stat calls.

    Returns dict with:
    - 'success' (bool) - False only when a recent-issue asset has no source file
    - 'message' (str)
    - 'copied' (list) - assets that were absent from the destination
    - 'refreshed' (list) - assets that were present but stale
    - 'missing' (list) - recent-issue refs with no source file (blocking)
    - 'warnings' (list) - older refs with no source file (non-blocking)
    """
    dirs = {
        "favicon": (favicon_src or FAVICON_SOURCE_DIR,
                    favicon_dest or FAVICON_DEST_DIR),
        "screenshot": (screenshot_src or SCREENSHOT_SOURCE_DIR,
                       screenshot_dest or SCREENSHOT_DEST_DIR),
        "og-image": (og_src or OG_IMAGE_SOURCE_DIR,
                     og_dest or OG_IMAGE_DEST_DIR),
    }

    refs = collect_asset_refs(bundledb_path, showcase_path)
    recent_refs, issue_numbers = _recent_asset_refs(bundledb_path, showcase_path)

    for _, dest_dir in dirs.values():
        os.makedirs(dest_dir, exist_ok=True)

    copied = []
    refreshed = []
    missing = []
    warnings = []

    for (kind, filename), title in sorted(refs.items()):
        src_dir, dest_dir = dirs[kind]
        src = os.path.join(src_dir, filename)
        dest = os.path.join(dest_dir, filename)

        if not os.path.exists(src):
            note = f"{kind} '{filename}' for '{title}' (source not found)"
            if (kind, filename) in recent_refs:
                missing.append(note)
            else:
                warnings.append(note)
            continue

        state = _copy_state(src, dest)
        if state is None:
            continue

        shutil.copy2(src, dest)
        (copied if state == "copied" else refreshed).append(f"{kind}: {filename}")

    if missing:
        return {
            "success": False,
            "message": f"Missing source files: {'; '.join(missing)}",
            "copied": copied,
            "refreshed": refreshed,
            "missing": missing,
            "warnings": warnings,
        }

    message = f"Reconciled {len(refs)} asset refs across the full DB"
    if issue_numbers:
        issues_str = " and #".join(str(i) for i in issue_numbers)
        message += f" (issues #{issues_str} blocking)"

    counts = []
    if copied:
        counts.append(f"copied {len(copied)}")
    if refreshed:
        counts.append(f"refreshed {len(refreshed)}")
    if warnings:
        counts.append(f"{len(warnings)} warnings")
    message += "; " + (", ".join(counts) if counts else "all assets already in place")

    return {
        "success": True,
        "message": message,
        "copied": copied,
        "refreshed": refreshed,
        "missing": [],
        "warnings": warnings,
    }
