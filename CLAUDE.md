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
│   └── showcase-cleared-sites.json  # Allowlist of sites that passed content review
├── showcase-review-results.json  # Full review results keyed by URL (flagged/error/clean)
├── showcase-review-report.html   # Generated HTML report of flagged and error sites
├── scripts/
│   └── capture-screenshot.js  # Puppeteer full-page screenshot capture
├── templates/              # Jinja2 (base.html, compose.html, result.html, editor.html, db_mgmt.html, 11ty-bundle-xx.md)
├── static/
│   ├── css/style.css       # Pico CSS overrides, warm color scheme, light/dark
│   ├── js/compose.js       # Form interactivity, modes, draft/image handling, validation
│   └── js/db_mgmt.js       # Fetch and render git commit history for DB management page
├── posts/
│   ├── history.json        # All posts, drafts, and failed posts (newest first)
│   └── draft_images/       # Persisted images keyed by draft/failed UUID
├── tests/                  # pytest suite (165 tests, uses responses + pytest-flask)
│   ├── conftest.py         # Shared fixtures (app, client, sample data, temp paths)
│   └── test_*.py           # Service, route, and data integrity tests
├── pytest.ini              # pytest config (testpaths, warnings)
├── package.json            # Node.js deps (Puppeteer, @sindresorhus/slugify for tests)
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
- **11ty Bundle Issue**: Same suffixes as 11ty, with `11ty Bundle Issue {issue_number}` prefix (dynamically resolved with the latest issue number from bundledb). Cursor placed after the prefix. Uses `{issue_number}` placeholder in `modes.py`, resolved via `_resolve_modes()` in `app.py`.
- **11ty BWE**: Same suffixes as 11ty, but with `Built with Eleventy: ` prefix. Cursor placed after the prefix.

Mode behavior:
- Selecting a mode auto-checks and locks the mode's platform checkboxes (currently Mastodon and Bluesky; Discord Showcase and Discord Content are not auto-selected by any mode).
- Per-platform textareas appear with prefix+suffix pre-filled.
- Switching between modes (including None) resets all textareas to their initial state — user text is not carried over.
- "Mirror across platforms" checkbox (default unchecked) enables cross-sync: typing in one platform textarea mirrors the body (preserving per-platform prefix/suffix) to the other. Checkbox is shown only when a mode is active and resets to unchecked on every mode switch.
- "Show Preview" button renders all platforms with highlighted @mentions, #hashtags, and URLs.
- Modes are stored on drafts/history entries as `mode` and `platform_texts` fields (backward compatible — absent for non-mode posts).

## Social Link Tagging

When posting about a BWE site, the app looks up the owner's Mastodon/Bluesky profiles and appends @-mentions to the per-platform textareas.

**Bundledb lookup** (`_lookup_social_links_from_bundledb()` in `app.py`):
- The `/social-links` endpoint first checks `bundledb.json` for blog post entries where `AuthorSite` matches the given URL.
- URL matching normalizes both sides: lowercase, strip trailing slash, strip `www.` prefix.
- If a match is found with `socialLinks` containing mastodon/bluesky URLs, converts them to @-mentions and returns immediately (no HTTP requests needed).
- Falls back to HTML scraping (below) only if no bundledb match is found.

**HTML scraping fallback** (`services/social_links.py`):
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

The `/editor` page (linked from the main page as "Bundle Editor") provides search and edit for entries across both `bundledb.json` and `showcase-data.json`, plus a create mode for adding new entries and a generate mode for creating the bundle issue markdown file. The editor page has a "Back to Social Posting" button, "Bundle Entry Editor" header, and right-justified "Check URL", "Run Latest", "Deploy", and "DB Mgmt" buttons in the header bar. Mode (Create Entry/Edit Entry/Edit Latest Issue/Generate Bundle Issue) is selected via radio buttons at the top, then type is selected (except in Edit Latest Issue and Generate Bundle Issue modes which hide the type selector). Switching between modes clears the type selection. In edit mode, fuzzy search (Fuse.js) over type-specific keys finds items. In create mode, selecting a type opens a blank form with auto-populated fields and cursor in the Title field. Fields are ordered per `FIELD_ORDER` in `editor.js` with manual-entry fields first, followed by fetch buttons, then auto-generated fields. Saves go to `POST /editor/save`, which creates backups of both `bundledb.json` and `showcase-data.json` on first save per session.

**Unified data with origin tracking**:
- `/editor/data` tags every entry with `_origin`: `"bundledb"` (bundledb only), `"both"` (site in both files), or `"showcase"` (showcase-data only).
- Showcase-only entries (in showcase-data.json but not bundledb.json) are normalized to PascalCase (`title`→`Title`, `link`→`Link`, etc.), given `Type: "site"`, and returned in a separate `showcase_only` array with `_showcaseIndex` pointing to their position in showcase-data.json.
- The frontend appends `showcase_only` entries to `allData`, making them searchable and editable alongside bundledb entries. Bundledb indices stay stable.
- Item cards show origin badges ("bundledb", "showcase", or both) to indicate where each entry lives.
- Search keys include `description` for all types, and cross-type search includes `Link` and `description`.
- Showcase-only entries use a dedicated `FIELD_ORDER["showcase"]`: Title, Link, Date, formattedDate, description, favicon, screenshotpath, leaderboardLink.
- Saving a showcase-only entry sends `{showcase_only: true, showcase_index: N}` — the backend converts PascalCase back to lowercase and updates showcase-data.json directly.
- Deleting a showcase-only entry removes it from showcase-data.json only. Remaining showcase-only entries in allData have their `_showcaseIndex` decremented.
- Saving a "both" entry syncs the `Skip` field to both bundledb.json and showcase-data.json.

**Create/Edit modes** (`editor.js` + `editor.html`):
- Mode radio buttons (Create Entry/Edit Entry/Edit Latest Issue/Generate Bundle Issue) at top of editor. Create Entry is the default.
- Switching between modes clears the type selection and hides all form elements.
- Create mode hides search/recent items and shows a blank form for the selected type.
- New items are auto-populated with `Date` (ISO), `formattedDate` (human-readable), `Issue` (current max from data), and `Type`. The `Type` field is hidden in create mode since it's already selected via the radio button.
- On create, cursor is auto-focused on the Title field.
- Create saves append to the end of the `bundledb.json` array (edit saves update in place).

**Edit latest issue mode** (`editor.js` + `editor.html`):
- Third mode radio button. Hides the type selector and shows a summary line with issue number and per-type counts (same style as the social posting page).
- Displays all entries for the latest issue number grouped into 4 sections (Blog Posts, Sites, Releases, Starters) with count in each heading.
- Search uses a cross-type Fuse index (searches Title and Author across all types). Clearing search restores the grouped sections.
- Clicking an item card sets `currentType` to the item's type before opening the edit form, so field order and save logic work correctly.
- Cancel clears search, restores the grouped view, and scrolls to top.
- After save/delete, the grouped view and Fuse index are refreshed.

**Generate Bundle Issue mode** (`editor.js` + `editor.html` + `services/blog_post.py`):
- Fourth mode radio button. Hides the type selector and shows the same issue summary line as Edit Latest Issue.
- Displays a large "Generate Bundle Issue" button at the top, followed by all entries for the latest issue grouped by type (Blog Posts, Sites, Releases, Starters).
- Blog post entries have checkboxes on the left for selecting highlights. Clicking the card toggles the checkbox. Selected cards get a highlighted border and background tint (`.item-card.selected`).
- Non-blog-post entries are read-only cards (no checkboxes, no click handlers).
- Clicking "Generate Bundle Issue" POSTs to `/create-blog-post` with `{ issue_number, date, highlights }`. The `highlights` array contains `{ author, author_site, title, link }` for each checked blog post.
- `create_blog_post()` in `services/blog_post.py` accepts an optional `highlights` parameter. When provided, replaces the `**.**` placeholder lines in the `## Highlights` section of the template with formatted entries: `**.** [Author](author_site) - [Title](link)`.
- The generated file opens in VS Code automatically.
- CSS styles: `.generate-item-row` (flex row for checkbox + card), `.generate-highlight-cb` (checkbox sizing), `.btn-generate-issue` (large button).

**Item card Source links** (`editor.js` + `style.css`):
- All item cards (edit, edit-latest, search results) show a "Source" link (float right, underlined, muted color) that opens the entry's URL in a new tab.
- `stopPropagation` on the link prevents triggering the card's edit-form click handler.

**Field order by type** (`FIELD_ORDER` in `editor.js`):
- **Blog post**: Issue, Type, Title, Link, Date, Author, Categories, [Fetch Description button], formattedDate, slugifiedAuthor, slugifiedTitle, description, AuthorSite, [Fetch/Refresh Author Info button], AuthorSiteDescription, socialLinks, favicon, rssLink.
- **Site**: Issue, Type, Title, Link, Date, formattedDate, [Fetch/Refresh Description, Favicon, Screenshot & Leaderboard button], description, favicon, screenshotpath, leaderboardLink.
- **Release**: Issue, Type, Title, Link, Date, formattedDate, [Fetch/Refresh Description button], description.
- **Starter**: Issue, Type, Title, Link, Demo, [Fetch/Refresh Description & Screenshot button], description, screenshotpath.
- **Showcase** (showcase-only entries): Title, Link, Date, formattedDate, description, favicon, screenshotpath, leaderboardLink.

**Auto-slugify** (create mode, `editor.js`):
- Title and Author fields auto-compute `slugifiedTitle` and `slugifiedAuthor` on blur.
- Client-side `slugify()` function matches `@sindresorhus/slugify` behavior: custom replacements map (German umlauts ö→oe/ä→ae/ü→ue, ligatures, special Latin chars), NFD decomposition with diacritic stripping, decamelization, contraction handling (`it's`→`its`), dash normalization. Python equivalent in `services/slugify.py` (used by `services/insights.py`).

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
- `POST /editor/screenshot` runs the script via `subprocess.run()` with 60s timeout.
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

**Content review** (`services/content_review.py`):
- When adding a site, AI reviews the site's content for hateful, discriminatory, or extremist opinions using Claude Haiku via the `anthropic` SDK.
- Runs in parallel with favicon, screenshot, description, and leaderboard fetches as a 5th promise in `fetchSiteData()`.
- `fetch_page_text(url)` fetches a page and extracts visible body text (strips nav, header, footer, aside, script, style elements), truncated to ~3000 chars.
- `find_subpages(url, soup)` identifies /about, /author, /beliefs pages and up to 10 blog post title links from the homepage.
- `review_content(url)` fetches homepage + subpages, concatenates text, sends to Claude Haiku. Returns `{"flagged": bool, "confidence": str, "summary": str, "pages_checked": int, "pages": [...]}`.
- On any error (no API key, network failure, unparseable response), returns `{"flagged": false, "error": "..."}` — the fetch flow continues normally.
- `POST /editor/content-review` endpoint — same pattern as `/editor/description`.
- Results shown in a banner (`#content-review-banner`) between the test-data-banner and search section: green for clear, red for flagged.
- Banner has three buttons: **Details** (opens modal showing pages fetched and review result), **Cancel Entry** (clears banner, form, and type selection), **Dismiss** (hides banner only).
- Banner auto-scrolls to top of page when displayed.
- Requires `ANTHROPIC_API_KEY` env var in `.env`.

**Showcase review** (`services/showcase_review.py`):
- Bulk scanner that reviews all sites in `showcase-data.json` using `review_content()` from `content_review.py`.
- Run as CLI: `python -m services.showcase_review [--test | --full | --site=URL | --report-only]`.
- `--test`: reviews 10 randomly selected non-allowlisted sites. `--full`: reviews all remaining. `--site=URL`: single ad-hoc review (not saved). `--report-only`: regenerates HTML report from existing results.
- **Results file** (`showcase-review-results.json`): dict with `reviewed` mapping normalized URLs to `{title, flagged, confidence, summary, pages_checked, pages}` or `{title, error}`.
- **Allowlist** (`data/showcase-cleared-sites.json`): dict of normalized URLs → `{cleared, title}`. Sites that pass review (not flagged, no error) are automatically added. Allowlisted sites are skipped on subsequent runs.
- **HTML report** (`showcase-review-report.html`): generated via `generate_report()`, shows flagged sites (sorted by confidence) and error sites (sorted by title).
- Review flags are surfaced in the editor: `/editor/data` includes a `review_flags` dict (URL → `"flagged"` or `"error"`), and item cards show red "flagged" or orange "error" badges.
- Rate limit handling: retries up to 3 times with exponential backoff (30s, 60s, 120s).

**Site save side-effects**:
- On create, site saves call `add_bwe_to_post(title, link)` to append the site to the BWE "TO BE POSTED" list, and prepend an entry to `showcase-data.json` with title, description, link, date, formattedDate, favicon, screenshotpath, and leaderboardLink.
- On edit, site saves sync the matching `showcase-data.json` entry (matched by link) with current title, description, favicon, screenshotpath, leaderboardLink, date, and formattedDate.
- Dates written to `showcase-data.json` are normalized to `YYYY-MM-DD` format (truncated from bundledb's full datetime via `[:10]`).

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
- The edit form has three save buttons: **Save** (save only), **Save & Run Latest** (save + end-session scripts + local server), **Save & Deploy** (save + end-session scripts + production deploy).
- The editor header has two standalone buttons: **Run Latest** and **Deploy** (same workflows without saving).
- All workflow results display in a modal overlay (`deploy-modal` in `editor.html`, styled via `.deploy-modal-overlay`/`.deploy-modal` in `style.css`).
- JS logic is shared via `runLatestFlow()` and `runDeployFlow()` functions in `editor.js`.

**Run Latest flow** (4 endpoints):
- `POST /editor/end-session` runs three tasks in parallel via `ThreadPoolExecutor`: `generate_issue_records()` (Python, `services/issue_records.py`), `generate_latest_data()` (Python, `services/latest_data.py`), and `generate_insights()` (Python, `services/insights.py`).
- `POST /editor/run-latest` starts `npm run latest` in the `11tybundle.dev` project (`ELEVENTY_PROJECT_DIR`) via `Popen`, watches stdout for `"Server at"` to detect readiness (30s timeout), then drains stdout in a daemon thread.
- `POST /editor/verify-site` runs post-build verification (see below). Called automatically after the server starts. On success, auto-commits and pushes `11tybundledb` changes via `_commit_and_push_bundledb()`.
- Modal shows script results, then "Starting local server...", then verification results and git result, then "View Local Site" button which opens `localhost:8080`.

**Deploy flow** (2 steps, same end-session + deploy endpoints):
- First calls `POST /editor/end-session` to run the same three parallel tasks as Run Latest (issue records, insights, latest data). Modal shows script results before proceeding.
- Then calls `POST /editor/deploy` which runs `npm run deploy` in `ELEVENTY_PROJECT_DIR` via `subprocess.run()` with 120s timeout, captures full stdout+stderr.
- On successful deploy, auto-commits and pushes `11tybundledb` changes via `_commit_and_push_bundledb()`. Git failures don't affect deploy success status.
- Response includes `git_result` with `success` and `message`. "Nothing to commit" is treated as success.
- Modal shows end-session results, then deploy output plus git result (success message or failure note), then "View 11tybundle.dev" button which opens `https://11tybundle.dev`.

**Post-build verification** (`services/verify_site.py`):
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
- Integrated into the Run Latest flow — runs automatically after the server starts, results shown in the modal before the "View Local Site" button.
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

**Backup system** (`_create_backup_with_pruning()` in `app.py`):
- On first save/delete/delete-test-entries per session, both `bundledb.json` and `showcase-data.json` are backed up with timestamped filenames (`prefix-YYYY-MM-DD--HHMMSS.json`).
- After creating a backup, auto-prunes oldest files to maintain a maximum of 25 backups per directory.
- Backup directories: `11tybundledb/bundledb-backups/` and `11tybundledb/showcase-data-backups/`.

## BWE Sites to Post Management

The compose page sidebar shows "Sites to Post" from `built-with-eleventy.md`. Each entry has:
- **M/B/D/C checkboxes**: per-platform selection (Mastodon/Bluesky/Discord Showcase/Discord Content). All unchecked by default. Clicking **Post** reads these checkboxes to set the main platform checkboxes and activate 11ty-bwe mode.
- **Post** button (or **Use** link if a draft exists): populates the compose form in 11ty-bwe mode with the selected platforms.
- **Del** button: removes the entry from the TO BE POSTED list via `POST /bwe-to-post/delete`. Shows a confirmation modal with Cancel focused by default.

**Per-platform tracking** (`services/bwe_list.py`):
- `ALL_PLATFORMS = ["B", "C", "D", "M"]`, `DEFAULT_PLATFORMS = []` (all unchecked). `C` = Discord Content channel.
- Markdown format uses optional `{PLATFORMS}` suffix: `[Name](url) {M,B}` or `[Name](url) {D}` or `[Name](url) {C}`. No suffix = default (empty).
- Posted entries: `2026-02-21 [Name](url) {M,B}`. Legacy `— status` format parsed for backward compat via `_extract_platforms_from_status()`.
- `_write_bwe_file(to_post, posted)` consolidates all file-writing (previously duplicated 5x).
- `update_bwe_after_post(name, url, posted_platforms, timestamp)`: partial posting support — remaining platforms stay in to_post, posted platforms merge with existing posted entry if present.
- `mark_bwe_posted()` retained as legacy wrapper calling `update_bwe_after_post()`.

**Sites Posted** sidebar shows colored platform badges (M=purple, B=blue, D=blurple, C=teal) for each posted entry.

## Testing

- **Visual testing via browser**: When making UI or layout changes, use the Claude in Chrome MCP tools to verify the result in the running app at `http://127.0.0.1:5555`. Navigate to the relevant page, interact as needed, and take screenshots to confirm the change looks correct before committing.
- **pytest suite**: 165 tests in `tests/` covering services, routes, and data integrity. Run with `pytest` (or `pytest -v` for verbose). Uses `responses` to mock HTTP calls and `pytest-flask` for the test client. Tests override file paths via `app.config` so they use temp directories — no production data is touched.
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
  - `test_insights.py` — Insights data + CSV generation, compared against JS output; slugify matching
  - `test_issue_records.py` — Issue records generation, compared against JS output
  - `test_latest_data.py` — Latest-issue data filtering, compared against JS output
  - `test_content_review.py` — AI content review service + endpoint (mocked Anthropic API)
  - `test_showcase_review.py` — Bulk showcase review scanner (load/save/allowlist/progress)
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
