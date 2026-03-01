# Socially Bundled

Personal publication management tool for 11tybundle.dev. What started as a social media cross-poster has evolved into the primary editorial interface for managing the 11ty Bundle -- a curated database of blog posts, sites, releases, and starters from the Eleventy community. Single Flask app with three surfaces: a Bundle Entry Editor, a Social Posting page with workflow integrations that tie the two together, and a Database Management page for visibility into the underlying data files.

This app is purpose-built for the sole use of the editor of 11tybundle.dev, running on a local machine with access to sibling project directories (`11tybundle.dev/`, `11tybundledb/`, etc.) and local Node.js tooling. It is not designed for general-purpose deployment.

**Reference codebase — dbtools**: The `dbtools/` directory at `/Users/Bob/Dropbox/Docs/Sites/11tybundle/dbtools/` contains the original Node.js tooling that this app has replaced. There are no remaining runtime dependencies on dbtools. All ported functionality (insights, issue records, latest data, screenshots, slugify) now runs from this project. When asked to port or replicate additional functionality from dbtools, read the source files there directly rather than inferring behavior from this project's code.

## Quick Start

```bash
cd social-posting
source .venv/bin/activate
python app.py  # runs on 127.0.0.1:5555
```

**Important**: Always prefix Python commands (pytest, python, etc.) with `source .venv/bin/activate &&` since the virtual environment is not automatically activated.

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
│   ├── discord_client.py   # Discord webhook API via requests (Showcase channel)
│   └── discord_content_client.py  # Discord Content channel (subclass of DiscordClient)
├── services/
│   ├── media.py            # process_uploads, cleanup_uploads, compress_for_bluesky
│   ├── link_card.py        # Open Graph metadata fetching
│   ├── social_links.py     # Extract Mastodon/Bluesky profiles from site HTML
│   ├── favicon.py          # Multi-strategy favicon fetching (existing/Google API/HTML extraction)
│   ├── description.py      # Multi-source meta description extraction (mirrors getdescription.js)
│   ├── rss_link.py         # RSS/Atom feed URL discovery (mirrors getrsslink.js)
│   ├── leaderboard.py      # 11ty Speedlify Leaderboard link check
│   ├── bwe_list.py         # Parse/modify built-with-eleventy.md (to-post/posted lists)
│   ├── slugify.py          # Python port of @sindresorhus/slugify (shared by editor auto-slugify and insights)
│   ├── insights.py         # Generate insightsdata.json + CSV files (ported from generate-insights.js)
│   ├── issue_records.py    # Generate issuerecords.json from bundledb (ported from genissuerecords.js)
│   ├── latest_data.py      # Generate latest-issue filtered data files (ported from generate-latest-data.js)
│   ├── blog_post.py        # Create bundle issue markdown from template with optional highlights
│   ├── content_review.py   # AI content review for site entries (Claude Haiku via anthropic SDK)
│   ├── showcase_review.py  # Bulk content review scanner for all showcase-data.json sites (CLI tool)
│   └── verify_site.py      # Post-build verification: checks _site HTML for entry presence and valid assets
├── data/
│   ├── insights-exclusions.json  # Exclusions for insights missing-data checks
│   ├── showcase-cleared-sites.json  # Allowlist of sites that passed content review
│   └── sveltiacms-sites.json    # Runtime: queued sites from SveltiaCMS showcase check
├── showcase-review-results.json  # Full review results keyed by URL (flagged/error/clean)
├── showcase-review-report.html   # Generated HTML report of flagged and error sites
├── scripts/
│   └── capture-screenshot.js  # Puppeteer full-page screenshot capture
├── templates/              # Jinja2 (base.html, compose.html, result.html, editor.html, db_mgmt.html, 11ty-bundle-xx.md)
├── static/
│   ├── css/style.css       # Pico CSS overrides, warm color scheme, light/dark
│   ├── js/compose.js       # Form interactivity, modes, draft/image handling, validation
│   └── js/db_mgmt.js       # Git commit history + SveltiaCMS showcase check modal
├── posts/
│   ├── history.json        # All posts, drafts, and failed posts (newest first)
│   └── draft_images/       # Persisted images keyed by draft/failed UUID
├── tests/                  # pytest suite (165 tests, uses responses + pytest-flask)
│   ├── conftest.py         # Shared fixtures (app, client, sample data, temp paths)
│   └── test_*.py           # Service, route, and data integrity tests
├── pytest.ini              # pytest config (testpaths, warnings)
├── package.json            # Node.js deps (Puppeteer, @sindresorhus/slugify for tests)
├── uploads/                # Temporary upload dir (cleaned after posting)
└── docs/                   # Reference docs (editor, social posting, workflows)
```

## Architecture

- **Platform abstraction**: `PlatformClient` ABC in `platforms/base.py`. Each platform implements `post()` and `validate_credentials()`. Factory in `__init__.py`.
- **Media flow**: Upload to `uploads/` temp dir -> for drafts/failed, copy to `posts/draft_images/<id>/` -> for posting, pass `MediaAttachment` to platform client -> cleanup.
- **History**: JSON file (`posts/history.json`). Entries prepended (newest first). Drafts have `is_draft: true`, failed posts have `is_failed: true` (or are detected as non-draft entries with empty `platforms` list). Both have an `images` array with filename/alt_text/mime_type metadata.
- **Mutual exclusivity**: Images and link cards cannot coexist. Enforced in JS via disabled fieldsets.
- **Modes system**: Extensible mode registry in `modes.py`. Each mode defines a label, auto-selected platforms, and per-platform prefixes/suffixes. Adding a new mode = adding a dict entry in `MODES`, no other changes needed.

## Social Posting

The compose page (`/`) supports cross-posting to Mastodon, Bluesky, Discord Showcase, and Discord Content channels. Modes (11ty, 11ty Bundle Issue, 11ty BWE) switch to per-platform textareas with pre-filled hashtags/mentions. Social link tagging auto-appends site owners' @-mentions when posting BWE sites (looks up bundledb first, falls back to HTML scraping). The sidebar shows BWE sites to post with per-platform checkboxes (M/B/D/C), posted entries with colored platform badges, drafts, and failed posts with retry support. For full details see `docs/social-posting-reference.md`.

## Bundledb Editor

The `/editor` page provides search and edit for entries across `bundledb.json` and `showcase-data.json`, with four modes: Create Entry, Edit Entry, Edit Latest Issue, and Generate Bundle Issue. Entries are tagged with `_origin` (bundledb/both/showcase). Features include: fuzzy search (Fuse.js), per-type field ordering, auto-slugify, author autocomplete with field propagation, per-type fetch buttons (description, favicon, screenshot, leaderboard, RSS, author info), AI content review for sites, duplicate link detection, Check URL modal, View JSON preview, skip checkbox, delete with confirmation, and test data guards. Site saves sync to `showcase-data.json` and add to BWE to-post list. For full details see `docs/editor-reference.md`.

## Build & Deploy Workflows

The editor integrates Run Latest (local preview) and Deploy (production) workflows via Save & Run Latest / Save & Deploy buttons (or standalone header buttons). Both start with end-session scripts (generate issue records, insights, latest data in parallel). Run Latest starts the local server, runs post-build verification against `_site`, and auto-commits/pushes `11tybundledb` on success. Deploy runs `npm run deploy` and auto-commits/pushes `11tybundledb`. Results display in a modal overlay. For full details see `docs/workflows-reference.md`.

## Database Management

The `/db-mgmt` page shows database statistics (per-type counts, authors, categories), backup file counts, and the 5 most recent git commits for each data file with newly added entry titles. Backups are created on first save per session (timestamped, auto-pruned to 25 max). For full details see `docs/workflows-reference.md`.

**SveltiaCMS Showcase Check**: The "Check SveltiaCMS" button fetches the SveltiaCMS showcase page (`sveltiacms.app`), extracts Eleventy sites from the VitePress data (hash map + lean.js), and filters out sites already in `showcase-data.json` or `sveltiacms-sites.json` (URL comparison normalizes protocol, `www.`, and trailing slashes). New sites appear in a modal with checkboxes — checked sites are queued for addition, unchecked sites are saved with `skip: true` so they don't reappear. The "Add Next Site (N)" button links to `/?sveltiacms=1`, which pre-fills the editor in Create + Site mode with the first non-skipped queued site's title and URL. Saving the entry in the editor automatically removes it from the queue.

## Testing

- **Visual testing via browser**: When making UI or layout changes, use the Claude in Chrome MCP tools to verify the result in the running app at `http://127.0.0.1:5555`.
- **pytest suite**: 224 tests in `tests/` covering services, routes, and data integrity. Run with `source .venv/bin/activate && pytest` (or `pytest -v` for verbose). Uses `responses` to mock HTTP calls and `pytest-flask` for the test client.
- **Path overrides for testing**: `app.py` uses `_get_path(key)` to read file paths from `app.config` with fallback to module-level constants. Tests set `app.config["BUNDLEDB_PATH"]`, `app.config["SHOWCASE_PATH"]`, etc. to temp directories. For `bwe_list.BWE_FILE`, tests use `monkeypatch.setattr`.
- **Adding tests**: When adding new services or routes, add corresponding test files. Mock external HTTP with `@responses.activate`. Use the `client` fixture for route tests and `app` fixture to access temp paths.

## Key Conventions

- All paths in `app.py` are `__file__`-relative via `_BASE_DIR` (not CWD-relative). Route functions read paths via `_get_path()` which checks `app.config` first (for test overrides), then falls back to the module-level constant.
- Image file inputs: the `<input type="file">` in the template has **no `name` attribute** — files are submitted via a dynamically-created hidden input in the JS submit handler.
- Alt text is required for all images (enforced client-side on submit). Bluesky images auto-compressed to fit 1MB limit.
- Character counting is grapheme-aware (`Intl.Segmenter`).
- Content warnings use radio buttons per platform (Mastodon/Bluesky: None, Sexual, Nudity, Graphic Media, Porn, Political; Discord: None or Spoiler).
- Static asset cache-busting: CSS and JS files use `?v={{ css_version }}` / `?v={{ js_version }}` query params (file mtime) via Flask context processor.
- **Git commits on main**: When committing to the `main` branch, always push to GitHub immediately after the commit.

## Configuration

Environment variables in `.env` (see `.env.example`):

- `MASTODON_INSTANCE_URL` / `MASTODON_ACCESS_TOKEN` (token needs `write:statuses` and `write:media` scopes)
- `BLUESKY_IDENTIFIER` / `BLUESKY_APP_PASSWORD`
- `DISCORD_WEBHOOK_URL` / `DISCORD_GUILD_ID` (Showcase channel webhook; guild ID used to construct message jump URLs)
- `DISCORD_WEBHOOK_URL_CONTENT` / `DISCORD_GUILD_ID_CONTENT` (Content channel webhook)
- `ANTHROPIC_API_KEY` (for AI content review of site entries; optional — review is skipped if not set)

## Tech Stack

- **Backend**: Flask, Mastodon.py, atproto, anthropic, requests, Pillow, BeautifulSoup4, python-dotenv
- **Frontend**: Jinja2, Pico CSS (CDN), vanilla JS, Fuse.js (CDN, editor search)
- **Tooling**: Node.js + Puppeteer (screenshot capture)
- **Testing**: pytest, responses (HTTP mocking), pytest-flask
- **No database** — flat JSON file for history, filesystem for images
