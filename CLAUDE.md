# Socially Bundled

Personal publication management tool for 11tybundle.dev. What started as a social media cross-poster has evolved into the primary editorial interface for managing the 11ty Bundle -- a curated database of blog posts, sites, releases, and starters from the Eleventy community. Single Flask app with three surfaces: a Bundle Entry Editor, a Social Posting page with workflow integrations that tie the two together, and a Database Management page for visibility into the underlying data files.

This app is purpose-built for the sole use of the editor of 11tybundle.dev, running on a local machine with access to sibling project directories (`dbtools/`, `11tybundle.dev/`, etc.) and local Node.js tooling. It is not designed for general-purpose deployment.

**Reference codebase — dbtools**: The `dbtools/` directory at `/Users/Bob/Dropbox/Docs/Sites/11tybundle/dbtools/` contains the original Node.js tooling that this app is progressively replacing. When asked to port or replicate functionality from dbtools, always read the source files there directly rather than inferring behavior from this project's code.

## Quick Start

```bash
cd social-posting
source .venv/bin/activate
python app.py  # runs on 127.0.0.1:5555
```

Launched via Raycast script at `~/Dropbox/Docs/Raycast/Scripts/bob-on-social.sh`.

## Project Structure

```
social-posting/
├── app.py                  # Flask routes, draft/post logic, history management
├── config.py               # Env vars, upload limits, allowed extensions
├── modes.py                # Mode registry (MODES dict, all_modes(), get_mode())
├── platforms/
│   ├── __init__.py         # get_platform() factory
│   ├── base.py             # MediaAttachment, LinkCard, PostResult, PlatformClient ABC
│   ├── mastodon_client.py  # Mastodon API via Mastodon.py
│   ├── bluesky_client.py   # Bluesky AT Protocol via atproto
│   └── discord_client.py   # Discord webhook API via requests
├── services/
│   ├── media.py            # process_uploads, cleanup_uploads, compress_for_bluesky
│   ├── link_card.py        # Open Graph metadata fetching
│   ├── social_links.py     # Extract Mastodon/Bluesky profiles from site HTML
│   ├── favicon.py          # Multi-strategy favicon fetching (existing/Google API/HTML extraction)
│   ├── description.py      # Multi-source meta description extraction (mirrors getdescription.js)
│   ├── rss_link.py         # RSS/Atom feed URL discovery (mirrors getrsslink.js)
│   ├── leaderboard.py      # 11ty Speedlify Leaderboard link check
│   └── bwe_list.py         # Parse/modify built-with-eleventy.md (to-post/posted lists)
├── scripts/
│   └── capture-screenshot.js  # Puppeteer full-page screenshot capture
├── templates/              # Jinja2 (base.html, compose.html, result.html, editor.html, db_mgmt.html)
├── static/
│   ├── css/style.css       # Pico CSS overrides, warm color scheme, light/dark
│   ├── js/compose.js       # Form interactivity, modes, draft/image handling, validation
│   └── js/db_mgmt.js       # Fetch and render git commit history for DB management page
├── posts/
│   ├── history.json        # All posts, drafts, and failed posts (newest first)
│   └── draft_images/       # Persisted images keyed by draft/failed UUID
├── tests/                  # pytest suite (113 tests, uses responses + pytest-flask)
│   ├── conftest.py         # Shared fixtures (app, client, sample data, temp paths)
│   └── test_*.py           # Service, route, and data integrity tests
├── pytest.ini              # pytest config (testpaths, warnings)
├── uploads/                # Temporary upload dir (cleaned after posting)
└── docs/                  # Requirements docs for features (retained across sessions)
```

## Architecture

- **Platform abstraction**: `PlatformClient` ABC in `platforms/base.py`. Each platform implements `post()` and `validate_credentials()`. Factory in `__init__.py`.
- **Media flow**: Upload to `uploads/` temp dir -> for drafts/failed, copy to `posts/draft_images/<id>/` -> for posting, pass `MediaAttachment` to platform client -> cleanup.
- **History**: JSON file (`posts/history.json`). Entries prepended (newest first). Drafts have `is_draft: true`, failed posts have `is_failed: true` (or are detected as non-draft entries with empty `platforms` list). Both have an `images` array with filename/alt_text/mime_type metadata.
- **Mutual exclusivity**: Images and link cards cannot coexist. Enforced in JS via disabled fieldsets.
- **Modes system**: Extensible mode registry in `modes.py`. Each mode defines a label, auto-selected platforms, and per-platform prefixes/suffixes. Adding a new mode = adding a dict entry in `MODES`, no other changes needed.

## Modes

Modes switch the UI from a single shared textarea to per-platform textareas, each pre-populated with platform-specific hashtags and mentions. Configured in `modes.py`.

Current modes:
- **11ty**: Adds `#11ty @11ty@neighborhood.11ty.dev` (Mastodon) and `@11ty.dev` (Bluesky) as suffixes. Cursor at start.
- **11ty BWE**: Same suffixes as 11ty, but with `Built with Eleventy: ` prefix. Cursor placed after the prefix.

Mode behavior:
- Selecting a mode auto-checks and locks the mode's platform checkboxes (currently Mastodon and Bluesky; Discord is not auto-selected by any mode).
- Per-platform textareas appear with prefix+suffix pre-filled.
- Switching between modes (including None) resets all textareas to their initial state — user text is not carried over.
- "Mirror across platforms" checkbox (default unchecked) enables cross-sync: typing in one platform textarea mirrors the body (preserving per-platform prefix/suffix) to the other. Checkbox is shown only when a mode is active and resets to unchecked on every mode switch.
- "Show Preview" button renders all platforms with highlighted @mentions, #hashtags, and URLs.
- Modes are stored on drafts/history entries as `mode` and `platform_texts` fields (backward compatible — absent for non-mode posts).

## Social Link Tagging

When posting about a BWE site, the app fetches the site's HTML to discover the owner's Mastodon/Bluesky profiles and appends @-mentions to the per-platform textareas.

**Backend** (`services/social_links.py`):
- `extract_social_links(url)` returns `{"mastodon": "@user@instance", "bluesky": "@handle"}` (empty strings if not found).
- Detection strategies (ported from `getsociallinks.js`): JSON-LD `sameAs` arrays, `<a rel="me">` links, URL pattern matching (`/@` / `/users/` for Mastodon, `bsky` hostname for Bluesky), CSS class/aria-label/title hints.
- Checks homepage, `/about/`, `/en/` — stops early after `/about/` if links found.
- URL-to-mention conversion: `https://instance.social/@user` → `@user@instance.social`; `https://bsky.app/profile/handle` → `@handle`.
- Exposed via `POST /social-links` endpoint (same pattern as `/link-preview`).

**Frontend** (`compose.js`):
- `fetchAndAppendSocialLinks(siteUrl)` POSTs to `/social-links`, appends returned mentions to per-platform textareas (skips duplicates), updates char counters.
- Called from BWE Post button handler (async after form population).
- Called on page load when a BWE draft is loaded via Use (detects `bwe-site-url` hidden field + active `11ty-bwe` mode).

## Failed Posts

When a post fails on any platform:
- The entry is saved to history with `is_failed: true` and images persisted for retry.
- The sidebar shows a red **FAILED** badge with **Retry** (reloads into compose form) and **Del** buttons.
- Legacy failed posts (pre-`is_failed` flag) are detected as non-draft entries with no successful platforms.

## Bundledb Editor

The `/editor` page (linked from the main page as "Bundle Editor") provides search and edit for `bundledb.json` items, plus a create mode for adding new entries. The editor page has a "Back to Social Posting" button, "Bundle Entry Editor" header, and right-justified "Check URL", "Run Latest", "Deploy", and "DB Mgmt" buttons in the header bar. Mode (Edit/Create) is selected via radio buttons at the top, then type is selected. Switching between modes clears the type selection. In edit mode, fuzzy search (Fuse.js) over type-specific keys finds items. In create mode, selecting a type opens a blank form with auto-populated fields and cursor in the Title field. Fields are ordered per `FIELD_ORDER` in `editor.js` with manual-entry fields first, followed by fetch buttons, then auto-generated fields. Saves go to `POST /editor/save`, which creates backups of both `bundledb.json` and `showcase-data.json` on first save per session.

**Edit/Create modes** (`editor.js` + `editor.html`):
- Mode radio buttons (Edit/Create) at top of editor. Create mode is the default.
- Switching between Edit and Create clears the type selection and hides all form elements.
- Create mode hides search/recent items and shows a blank form for the selected type.
- New items are auto-populated with `Date` (ISO), `formattedDate` (human-readable), `Issue` (current max from data), and `Type`. The `Type` field is hidden in create mode since it's already selected via the radio button.
- On create, cursor is auto-focused on the Title field.
- Create saves append to the end of the `bundledb.json` array (edit saves update in place).

**Field order by type** (`FIELD_ORDER` in `editor.js`):
- **Blog post**: Issue, Type, Title, Link, Date, Author, Categories, [Fetch Description button], formattedDate, slugifiedAuthor, slugifiedTitle, description, AuthorSite, [Fetch/Refresh Author Info button], AuthorSiteDescription, socialLinks, favicon, rssLink.
- **Site**: Issue, Type, Title, Link, Date, formattedDate, [Fetch/Refresh Description, Favicon, Screenshot & Leaderboard button], description, favicon, screenshotpath, leaderboardLink.
- **Release**: Issue, Type, Title, Link, Date, formattedDate, [Fetch/Refresh Description button], description.
- **Starter**: Issue, Type, Title, Link, Demo, [Fetch/Refresh Description & Screenshot button], description, screenshotpath.

**Auto-slugify** (create mode, `editor.js`):
- Title and Author fields auto-compute `slugifiedTitle` and `slugifiedAuthor` on blur.
- Client-side `slugify()` function matches `@sindresorhus/slugify` behavior: custom replacements map (German umlauts ö→oe/ä→ae/ü→ue, ligatures, special Latin chars), NFD decomposition with diacritic stripping, decamelization, contraction handling (`it's`→`its`), dash normalization.

**View JSON button** (create and edit modes, `editor.js`):
- "View JSON" button in the save button row opens a read-only panel showing the pretty-printed JSON entry.
- For site entries, also shows the `showcase-data.json` entry below.
- Clicking again refreshes the preview; panel closes on save.

**Duplicate link detection** (create mode, `editor.js`):
- On Link field blur, checks for existing entries with the same normalized link across `bundledb.json` and `showcase-data.json`.
- Save is blocked if a duplicate is found, with a modal showing the duplicate entry type, title, and which file(s) it was found in.
- URL normalization (`normalizeLink`): lowercases, strips trailing slashes, prepends `https://` if no protocol, strips `www.` prefix — so `https://www.example.com` and `https://example.com` are treated as identical.

**Check URL** (`editor.js` + `app.py`):
- "Check URL" button in the editor header opens a modal with a URL input field, Check and Close buttons.
- `POST /editor/check-url` normalizes the URL (lowercase, strip trailing slashes, ensure protocol, strip `www.`) and searches both `bundledb.json` (by `Link`) and `showcase-data.json` (by `link`).
- Results show which file(s) contain the URL, with entry type and title.
- Modal dismisses via Close button or Escape key.

**Delete entry** (edit mode, `editor.js` + `app.py`):
- "DELETE ENTRY" red button in the skip checkbox row (right-justified).
- Custom confirmation modal with "ARE YOU SURE YOU WANT TO DELETE THE [type] NAMED [title]?" message. Cancel button is focused by default (Enter does not delete).
- `POST /editor/delete` removes the entry from `bundledb.json` (and from `showcase-data.json` for sites).

**Delete test entries** (edit mode, `editor.js` + `app.py`):
- "DELETE ALL TEST ENTRIES" button appears next to DELETE ENTRY only when entries with "bobdemo99" in their title exist.
- `POST /editor/delete-test-entries` removes all matching entries from both `bundledb.json` and `showcase-data.json`.

**Test data guards** (`editor.js` + `editor.html`):
- When any type is selected (edit or create mode), an orange warning banner appears below the type selector if any entries with "bobdemo99" in their title exist. Banner shows the count and a DELETE ALL TEST ITEMS button.
- **Run Latest guard**: Clicking Run Latest (standalone or Save & Run Latest) when test data is present shows a warning modal ("Test Data Present") with Cancel and Proceed buttons. Proceed is focused by default.
- **Deploy guard**: Clicking Deploy (standalone or Save & Deploy) when test data is present shows a blocking modal ("UNABLE TO DEPLOY WHEN TEST DATA IS PRESENT") with DELETE TEST ITEMS and Close buttons. DELETE TEST ITEMS is focused by default and calls the delete-test-entries endpoint.
- Banner and guards refresh after test entries are deleted. Banner hides on mode switch.

**Skip checkbox** (edit mode only):
- A "Skip (exclude from site generation)" checkbox appears at the top of the edit form.
- When checked, adds `Skip: true` to the saved item.

**Description extraction** (`services/description.py`):
- `extract_description(url)` fetches a page and extracts the description using a multi-source fallback chain mirroring `dbtools/lib/getdescription.js`: meta description → Open Graph → Twitter Card → Dublin Core → Schema.org microdata → JSON-LD.
- Sanitizes output (removes HTML tags, control characters, zero-width characters; escapes ampersands/quotes; converts markdown links to HTML; truncates to 300 chars).
- YouTube URLs return "YouTube video" without fetching.
- Exposed via `POST /editor/description`.

**Fetch buttons** (per-type, create and edit):
- **Blog posts**: "Fetch Description" button after Categories (hidden if description already populated in edit mode). Fetches blog post description from the Link URL.
- **Sites**: "Fetch Description, Favicon, Screenshot & Leaderboard" button after Date. Fetches all four in parallel from the Link URL. Shows "Refresh..." when all fields are already populated.
- **Releases**: "Fetch Description" button after Date. Shows "Refresh Description" when description is already populated.
- **Starters**: "Fetch Description & Screenshot" button after Demo. Fetches both from the Demo URL (not the GitHub link). Shows "Refresh..." when both fields are populated.
- All fetch buttons use a `lastFetchedUrl` guard to prevent redundant fetches; clicking the button resets this to allow re-fetching.

**Author autocomplete** (blog post create):
- Author field uses a `<datalist>` populated from all unique authors in the database.
- Tab-completion auto-fills when there's exactly one fuzzy match.
- Selecting an existing author auto-fills empty fields (AuthorSite, AuthorSiteDescription, favicon, rssLink, socialLinks) from the most recent post by that author, and renames the author info button to "Refresh Author Info".

**Author info fetching** (blog posts, create and edit):
- AuthorSite auto-populates with the origin of the blog post Link URL when empty (e.g., `https://example.com/blog/post` → `https://example.com`). Triggers both at form render time and when a new author name is entered (on Author field blur). Editable since the author's site may differ.
- "Fetch Author Info" button appears after AuthorSite for new authors (not in database).
- "Refresh Author Info" button appears for existing authors (after autocomplete populates fields).
- Both buttons call `POST /editor/author-info` with the AuthorSite URL, which fetches in parallel: AuthorSiteDescription (via description service), socialLinks (via social_links service), favicon (via favicon service), rssLink (via rss_link service).
- Only fills empty fields (won't overwrite existing values).

**RSS link discovery** (`services/rss_link.py`):
- `extract_rss_link(url)` mirrors `dbtools/lib/getrsslink.js`: extracts origin, looks for `<link type="application/rss+xml">` or `<link type="application/atom+xml">` in the HTML head, then probes common feed paths (`/feed.xml`, `/rss.xml`, `/index.xml`, etc.).
- Validates probed paths by checking response content looks like a feed (not an HTML error page).

**Categories checkbox grid** (blog posts):
- Categories rendered as a 5-column checkbox grid using CSS `grid-auto-flow: column` with dynamic row count, so alphabetical order flows down each column.
- Display aliases shorten long category names without affecting stored values: "Internationalization" → "i18n", "Migrating to Eleventy" → "Migrating to 11ty", "The 11ty Conference 2024" → "11ty Conf 2024" (configured in `categoryDisplayNames` in `editor.js`).
- Includes an "Add new category" input + button for dynamically adding categories.
- Pre-checks categories that exist on the current item.

**Favicon fetching** (`services/favicon.py`):
- Tries existing file → Google API (`s2/favicons`) → HTML extraction (prioritizing SVG, large PNG, apple-touch-icon). Non-SVG/ICO images resized to 64x64 PNG via Pillow. Saves to `11tybundledb/favicons/` and copies to `_site/img/favicons/`.
- Exposed via `POST /editor/favicon`.

**Screenshot capture** (`scripts/capture-screenshot.js`):
- Puppeteer captures full-page JPEG at 1920x1080 with `networkidle0` + 3s delay. Saves to `11tybundledb/screenshots/` and `content/screenshots/`. Returns JSON with filename and path.
- `POST /editor/screenshot` runs the script via `subprocess.run()` with 60s timeout and `NODE_PATH` set to `dbtools/node_modules/` (required because the script lives in `social-posting/scripts/` but Puppeteer is installed in `dbtools/`).
- `GET /editor/screenshot-preview/<filename>` serves captured screenshots for inline preview.

**Screenshot data separation**:
- `screenshotpath` is stored only in `showcase-data.json`, not in `bundledb.json`.
- `GET /editor/data` returns `{"bundledb": [...], "showcase": [...]}`. Site entries in `bundledb` have `screenshotpath` merged from `showcase-data.json` (matched by link). The `showcase` array is used client-side for duplicate link detection.
- On save (create or edit), `screenshotpath` is stripped from the item before writing to `bundledb.json` and written only to `showcase-data.json`.

**Leaderboard link check** (`services/leaderboard.py`):
- `check_leaderboard_link(url)` probes `https://www.11ty.dev/speedlify/<normalized-domain>` to check if a site appears on the 11ty Speedlify Leaderboard.
- Normalizes hostname: strips `www.`, replaces `.` and `/` with `-`. Tries variations with/without `www-` prefix and trailing slash.
- Returns the leaderboard URL string if found (HTTP 200), or `None`.
- `POST /editor/leaderboard` endpoint — same pattern as `/editor/description`.
- `leaderboardLink` is stored only in `showcase-data.json` (same pattern as `screenshotpath`).
- Fetched in parallel with favicon, screenshot, and description in the site fetch flow.

**Site save side-effects**:
- On create, site saves call `add_bwe_to_post(title, link)` to append the site to the BWE "TO BE POSTED" list, and prepend an entry to `showcase-data.json` with title, description, link, date, formattedDate, favicon, screenshotpath, and leaderboardLink.
- On edit, site saves sync the matching `showcase-data.json` entry (matched by link) with current title, description, favicon, screenshotpath, leaderboardLink, date, and formattedDate.

**Custom field labels** (`fieldDisplayNames` and `fieldLabel()` in `editor.js`):
- `Link` shows as "GitHub repo link" for release/starter types.
- `Demo` shows as "Link to demo site" for starter type.
- CamelCase field names display with spaces: `formattedDate` → "Formatted Date", `slugifiedAuthor` → "Slugified Author", `slugifiedTitle` → "Slugified Title", `AuthorSite` → "Author Site", `AuthorSiteDescription` → "Author Site Description".

**Author-field propagation** (edit mode, `editor.js` + `app.py`):
- When saving a blog post edit, `buildPropagation()` compares original item (snapshotted as `originalItem` when the form opens) against edited values.
- Checks `PROPAGATABLE_FIELDS` (AuthorSiteDescription, rssLink, favicon) and `PROPAGATABLE_SOCIAL` (mastodon, bluesky, youtube, github, linkedin) for empty→non-empty transitions.
- If any newly-filled fields exist, scans `allData` for other blog posts by the same `Author` that also lack those fields.
- Shows a `confirm()` dialog with field names and affected post count.
- If confirmed, sends `propagate: [{index, field, value}, ...]` array in the save payload.
- Backend iterates `propagate` entries, handles both top-level fields and `socialLinks.*` sub-fields, writes once.
- Response includes `propagated` count; client syncs changes into local `allData` and shows status message.

**Build & deploy workflows** (`editor.js` + `app.py`):
- The edit form has three save buttons: **Save** (save only), **Save & Run Latest** (save + end-session scripts + local server), **Save & Deploy** (save + production deploy).
- The editor header has two standalone buttons: **Run Latest** and **Deploy** (same workflows without saving).
- All workflow results display in a modal overlay (`deploy-modal` in `editor.html`, styled via `.deploy-modal-overlay`/`.deploy-modal` in `style.css`).
- JS logic is shared via `runLatestFlow()` and `runDeployFlow()` functions in `editor.js`.

**Run Latest flow** (3 endpoints):
- `POST /editor/end-session` runs three dbtools scripts in parallel via `ThreadPoolExecutor`: `lib/genissuerecords.js`, `generate-insights.js` (pipes `"1\n"` to stdin for auto-select), `generate-latest-data.js`. All run with `cwd=DBTOOLS_DIR` and `NODE_PATH` set.
- `POST /editor/run-latest` starts `npm run latest` in the `11tybundle.dev` project (`ELEVENTY_PROJECT_DIR`) via `Popen`, watches stdout for `"Server at"` to detect readiness (30s timeout), then drains stdout in a daemon thread.
- Modal shows script results, then "Starting local server...", then "View Local Site" button which opens `localhost:8080`.

**Deploy flow** (1 endpoint):
- `POST /editor/deploy` runs `npm run deploy` in `ELEVENTY_PROJECT_DIR` via `subprocess.run()` with 120s timeout, captures full stdout+stderr.
- On successful deploy, auto-commits and pushes changed files in the `11tybundledb` repo (`BUNDLEDB_DIR`): `git add -A`, `git commit -m "New entries saved"`, `git push`. Git failures don't affect deploy success status.
- Response includes `git_result` with `success` and `message`. "Nothing to commit" is treated as success.
- Modal shows deploy output plus git result (success message or failure note), then "View 11tybundle.dev" button which opens `https://11tybundle.dev`.

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

**Backup system** (`_create_backup_with_pruning()` in `app.py`):
- On first save/delete/delete-test-entries per session, both `bundledb.json` and `showcase-data.json` are backed up with timestamped filenames (`prefix-YYYY-MM-DD--HHMMSS.json`).
- After creating a backup, auto-prunes oldest files to maintain a maximum of 25 backups per directory.
- Backup directories: `11tybundledb/bundledb-backups/` and `11tybundledb/showcase-data-backups/`.

## BWE Sites to Post Management

The compose page sidebar shows "Sites to Post" from `built-with-eleventy.md`. Each entry has:
- **Post** button (or **Use** link if a draft exists): populates the compose form in 11ty-bwe mode.
- **Del** button: removes the entry from the TO BE POSTED list via `POST /bwe-to-post/delete`. Shows a confirmation modal with Cancel focused by default.
- Backend: `delete_bwe_to_post(name, url)` in `services/bwe_list.py` parses and rewrites the markdown file.

## Testing

- **Visual testing via browser**: When making UI or layout changes, use the Claude in Chrome MCP tools to verify the result in the running app at `http://127.0.0.1:5555`. Navigate to the relevant page, interact as needed, and take screenshots to confirm the change looks correct before committing.
- **pytest suite**: 113 tests in `tests/` covering services, routes, and data integrity. Run with `pytest` (or `pytest -v` for verbose). Uses `responses` to mock HTTP calls and `pytest-flask` for the test client. Tests override file paths via `app.config` so they use temp directories — no production data is touched.
- **Test structure**:
  - `conftest.py` — Flask test client, temp file fixtures, sample data
  - `test_description.py` — description extraction + sanitization
  - `test_social_links.py` — Mastodon/Bluesky detection + mention conversion
  - `test_bwe_list.py` — BWE markdown parsing + mutation
  - `test_rss_link.py` — RSS/Atom feed discovery
  - `test_leaderboard.py` — Speedlify slug generation + probing
  - `test_link_card.py` — OG metadata extraction
  - `test_editor_routes.py` — Editor save/delete/check-url/data endpoints
  - `test_history_routes.py` — Draft/post lifecycle, link preview, social links
  - `test_data_integrity.py` — Round-trip, schema, showcase sync, backups
- **Path overrides for testing**: `app.py` uses `_get_path(key)` to read file paths from `app.config` with fallback to module-level constants. Tests set `app.config["BUNDLEDB_PATH"]`, `app.config["SHOWCASE_PATH"]`, etc. to temp directories. For `bwe_list.BWE_FILE`, tests use `monkeypatch.setattr`.
- **Adding tests**: When adding new services or routes, add corresponding test files. Mock external HTTP with `@responses.activate`. Use the `client` fixture for route tests and `app` fixture to access temp paths.

## Key Conventions

- All paths in `app.py` are `__file__`-relative via `_BASE_DIR` (not CWD-relative). Route functions read paths via `_get_path()` which checks `app.config` first (for test overrides), then falls back to the module-level constant.
- `config.py` uses `__file__`-relative path for `UPLOAD_FOLDER`.
- Image file inputs: the `<input type="file">` in the template has **no `name` attribute** — files are submitted via a dynamically-created hidden input in the JS submit handler. This prevents an empty file part from misaligning alt text indices in `process_uploads`.
- Alt text is required for all images (enforced client-side on submit).
- Bluesky images auto-compressed to fit 1MB limit.
- Character counting is grapheme-aware (`Intl.Segmenter`).
- Content warnings use radio buttons per platform. Mastodon: None, Sexual, Nudity, Graphic Media, Porn, Political (human-readable strings as spoiler text). Bluesky: same options (API label identifiers). Discord: None or Spoiler (wraps text in `||spoiler||` syntax with `**CW:**` header).
- Draft deletion route (`/draft/<id>/delete`) handles drafts, failed posts, and legacy failed entries.
- Sidebar post cards show badges (DRAFT/FAILED/platform), action buttons, 50-char text preview, and timestamp.
- Static asset cache-busting: CSS and JS files use `?v={{ css_version }}` / `?v={{ js_version }}` query params (file mtime) via Flask context processor.

## Configuration

Environment variables in `.env` (see `.env.example`):

- `MASTODON_INSTANCE_URL` / `MASTODON_ACCESS_TOKEN` (token needs `write:statuses` and `write:media` scopes)
- `BLUESKY_IDENTIFIER` / `BLUESKY_APP_PASSWORD`
- `DISCORD_WEBHOOK_URL` / `DISCORD_GUILD_ID` (webhook posts to a channel; guild ID used to construct message jump URLs)

## Tech Stack

- **Backend**: Flask, Mastodon.py, atproto, requests, Pillow, BeautifulSoup4, python-dotenv
- **Frontend**: Jinja2, Pico CSS (CDN), vanilla JS, Fuse.js (CDN, editor search)
- **Tooling**: Node.js + Puppeteer (screenshot capture)
- **Testing**: pytest, responses (HTTP mocking), pytest-flask
- **No database** — flat JSON file for history, filesystem for images
