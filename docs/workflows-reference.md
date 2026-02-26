# Workflows Reference

Detailed reference for build/deploy workflows, post-build verification, database management page, and backup system. See CLAUDE.md for a summary.

## Build & Deploy Workflows

`editor.js` + `app.py`:
- The edit form has three save buttons: **Save** (save only), **Save & Run Latest** (save + end-session scripts + local server), **Save & Deploy** (save + end-session scripts + production deploy).
- The editor header has two standalone buttons: **Run Latest** and **Deploy** (same workflows without saving).
- All workflow results display in a modal overlay (`deploy-modal` in `editor.html`, styled via `.deploy-modal-overlay`/`.deploy-modal` in `style.css`).
- JS logic is shared via `runLatestFlow()` and `runDeployFlow()` functions in `editor.js`.

### Run Latest Flow (4 endpoints)

- `POST /editor/end-session` runs three tasks in parallel via `ThreadPoolExecutor`: `generate_issue_records()` (Python, `services/issue_records.py`), `generate_latest_data()` (Python, `services/latest_data.py`), and `generate_insights()` (Python, `services/insights.py`).
- `POST /editor/run-latest` starts `npm run latest` in the `11tybundle.dev` project (`ELEVENTY_PROJECT_DIR`) via `Popen`, watches stdout for `"Server at"` to detect readiness (30s timeout), then drains stdout in a daemon thread.
- `POST /editor/verify-site` runs post-build verification (see below). Called automatically after the server starts. On success, auto-commits and pushes `11tybundledb` changes via `_commit_and_push_bundledb()`.
- Modal shows script results, then "Starting local server...", then verification results and git result, then "View Local Site" button which opens `localhost:8080`.

### Deploy Flow (2 steps)

- First calls `POST /editor/end-session` to run the same three parallel tasks as Run Latest (issue records, insights, latest data). Modal shows script results before proceeding.
- Then calls `POST /editor/deploy` which runs `npm run deploy` in `ELEVENTY_PROJECT_DIR` via `subprocess.run()` with 120s timeout, captures full stdout+stderr.
- On successful deploy, auto-commits and pushes `11tybundledb` changes via `_commit_and_push_bundledb()`. Git failures don't affect deploy success status.
- Response includes `git_result` with `success` and `message`. "Nothing to commit" is treated as success.
- Modal shows end-session results, then deploy output plus git result (success message or failure note), then "View 11tybundle.dev" button which opens `https://11tybundle.dev`.

## Post-Build Verification

`services/verify_site.py`:
- Parses the static `_site` directory (no browser needed) to confirm recently added entries rendered correctly.
- `verify_latest_issue()`: finds entries with the highest issue number in bundledb, checks them against the built HTML.
- `verify_by_date(date_str)`: finds entries matching a `YYYY-MM-DD` date (also accepts "today"/"yesterday").
- Checks per entry type:
  - **Blog posts**: title present in "From the firehose" section of `_site/index.html`, favicon file exists in `_site/img/favicons/`.
  - **Sites**: title in "Recent sites" section, favicon exists, showcase card found in `_site/showcase/index.html`, screenshot file exists in `_site/img/screenshots/`.
  - **Releases**: title in "Recent releases" section.
  - **Starters**: excluded (sort by GitHub modification date, not bundledb date).
- Home page sections limited to 11 entries each; entries beyond that are skipped with a note.
- Also available as a CLI: `python3 -m services.verify_site [YYYY-MM-DD]`.
- Integrated into the Run Latest flow -- runs automatically after the server starts, results shown in the modal before the "View Local Site" button.
- On successful verification (both Run Latest flow and `/verify-site` skill), `_commit_and_push_bundledb()` auto-commits and pushes all `11tybundledb` changes. Skipped on verification failure.

## Database Management

The `/db-mgmt` page (linked from the editor header as "DB Mgmt") provides read-only visibility into the two main data files and their backup/git history.

**Database Statistics** (`_compute_db_stats()` in `app.py`):
- bundledb.json: total entries, per-type counts (Blog Posts, Sites, Releases, Starters), unique authors, categories.
- showcase-data.json: total entries.

**Backup Files** (`_compute_backup_info()` in `app.py`):
- Displays file count and oldest backup date for both `bundledb-backups/` and `showcase-data-backups/` directories.

**Recent Git Commits** (`_get_commit_history()` + `_find_added_entries()` in `app.py`, rendered by `db_mgmt.js`):
- Shows the 5 most recent commits to each file in the `11tybundledb` git repo.
- Each commit card displays short SHA (linked to GitHub), date, and a list of newly added entry titles (computed by diffing the file between the commit and its parent).
- Commit data fetched asynchronously via `GET /db-mgmt/commits` to keep page load fast.

## Backup System

`_create_backup_with_pruning()` in `app.py`:
- On first save/delete/delete-test-entries per session, both `bundledb.json` and `showcase-data.json` are backed up with timestamped filenames (`prefix-YYYY-MM-DD--HHMMSS.json`).
- After creating a backup, auto-prunes oldest files to maintain a maximum of 25 backups per directory.
- Backup directories: `11tybundledb/bundledb-backups/` and `11tybundledb/showcase-data-backups/`.
