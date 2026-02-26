# Editor Reference

Detailed reference for the Bundle Entry Editor (`/editor` page). See CLAUDE.md for a summary.

## Unified Data with Origin Tracking

- `/editor/data` tags every entry with `_origin`: `"bundledb"` (bundledb only), `"both"` (site in both files), or `"showcase"` (showcase-data only).
- Showcase-only entries (in showcase-data.json but not bundledb.json) are normalized to PascalCase (`title`->`Title`, `link`->`Link`, etc.), given `Type: "site"`, and returned in a separate `showcase_only` array with `_showcaseIndex` pointing to their position in showcase-data.json.
- The frontend appends `showcase_only` entries to `allData`, making them searchable and editable alongside bundledb entries. Bundledb indices stay stable.
- Item cards show origin badges ("bundledb", "showcase", or both) to indicate where each entry lives.
- Search keys include `description` for all types, and cross-type search includes `Link` and `description`.
- Showcase-only entries use a dedicated `FIELD_ORDER["showcase"]`: Title, Link, Date, formattedDate, description, favicon, screenshotpath, leaderboardLink.
- Saving a showcase-only entry sends `{showcase_only: true, showcase_index: N}` -- the backend converts PascalCase back to lowercase and updates showcase-data.json directly.
- Deleting a showcase-only entry removes it from showcase-data.json only. Remaining showcase-only entries in allData have their `_showcaseIndex` decremented.
- Saving a "both" entry syncs the `Skip` field to both bundledb.json and showcase-data.json.

## Create/Edit Modes

- Mode radio buttons (Create Entry/Edit Entry/Edit Latest Issue/Generate Bundle Issue) at top of editor. Create Entry is the default.
- Switching between modes clears the type selection and hides all form elements.
- Create mode hides search/recent items and shows a blank form for the selected type.
- New items are auto-populated with `Date` (ISO), `formattedDate` (human-readable), `Issue` (current max from data), and `Type`. The `Type` field is hidden in create mode since it's already selected via the radio button.
- On create, cursor is auto-focused on the Title field.
- Create saves append to the end of the `bundledb.json` array (edit saves update in place).

## Edit Latest Issue Mode

- Third mode radio button. Hides the type selector and shows a summary line with issue number and per-type counts.
- Displays all entries for the latest issue number grouped into 4 sections (Blog Posts, Sites, Releases, Starters) with count in each heading.
- Search uses a cross-type Fuse index (searches Title and Author across all types). Clearing search restores the grouped sections.
- Clicking an item card sets `currentType` to the item's type before opening the edit form, so field order and save logic work correctly.
- Cancel clears search, restores the grouped view, and scrolls to top.
- After save/delete, the grouped view and Fuse index are refreshed.

## Generate Bundle Issue Mode

- Fourth mode radio button. Hides the type selector and shows the same issue summary line as Edit Latest Issue.
- Displays a large "Generate Bundle Issue" button at the top, followed by all entries for the latest issue grouped by type.
- Blog post entries have checkboxes on the left for selecting highlights. Clicking the card toggles the checkbox. Selected cards get a highlighted border and background tint (`.item-card.selected`).
- Non-blog-post entries are read-only cards (no checkboxes, no click handlers).
- Clicking "Generate Bundle Issue" POSTs to `/create-blog-post` with `{ issue_number, date, highlights }`. The `highlights` array contains `{ author, author_site, title, link }` for each checked blog post.
- `create_blog_post()` in `services/blog_post.py` accepts an optional `highlights` parameter. When provided, replaces the `**.**` placeholder lines in the `## Highlights` section of the template with formatted entries: `**.** [Author](author_site) - [Title](link)`.
- The generated file opens in VS Code automatically.
- CSS styles: `.generate-item-row` (flex row for checkbox + card), `.generate-highlight-cb` (checkbox sizing), `.btn-generate-issue` (large button).

## Item Card Source Links

- All item cards show a "Source" link (float right, underlined, muted color) that opens the entry's URL in a new tab.
- `stopPropagation` on the link prevents triggering the card's edit-form click handler.

## Field Order by Type

`FIELD_ORDER` in `editor.js`:
- **Blog post**: Issue, Type, Title, Link, Date, Author, Categories, [Fetch Description button], formattedDate, slugifiedAuthor, slugifiedTitle, description, AuthorSite, [Fetch/Refresh Author Info button], AuthorSiteDescription, socialLinks, favicon, rssLink.
- **Site**: Issue, Type, Title, Link, Date, formattedDate, [Fetch/Refresh Description, Favicon, Screenshot & Leaderboard button], description, favicon, screenshotpath, leaderboardLink.
- **Release**: Issue, Type, Title, Link, Date, formattedDate, [Fetch/Refresh Description button], description.
- **Starter**: Issue, Type, Title, Link, Demo, [Fetch/Refresh Description & Screenshot button], description, screenshotpath.
- **Showcase** (showcase-only entries): Title, Link, Date, formattedDate, description, favicon, screenshotpath, leaderboardLink.

## Auto-Slugify

Create mode, `editor.js`:
- Title and Author fields auto-compute `slugifiedTitle` and `slugifiedAuthor` on blur.
- Client-side `slugify()` function matches `@sindresorhus/slugify` behavior with `decamelize: false`: custom replacements map (German umlauts, ligatures, special Latin chars), NFD decomposition with diacritic stripping, contraction handling, dash normalization. Python equivalent in `services/slugify.py` (used by `services/insights.py`).

## View JSON Button

Create and edit modes, `editor.js`:
- "View JSON" button in the save button row opens a read-only panel showing the pretty-printed JSON entry.
- For site entries, also shows the `showcase-data.json` entry below.
- Clicking again refreshes the preview; panel closes on save.

## Duplicate Link Detection

Create mode, `editor.js`:
- On Link field blur, checks for existing entries with the same normalized link across `bundledb.json` and `showcase-data.json`.
- Save is blocked if a duplicate is found, with a modal showing the duplicate entry type, title, and which file(s) it was found in.
- URL normalization (`normalizeLink`): lowercases, strips trailing slashes, prepends `https://` if no protocol, strips `www.` prefix.

## Check URL

- "Check URL" button in the editor header opens a modal with a URL input field, Check and Close buttons.
- `POST /editor/check-url` normalizes the URL and searches both `bundledb.json` (by `Link`) and `showcase-data.json` (by `link`).
- Results show which file(s) contain the URL, with entry type and title.
- Modal dismisses via Close button or Escape key.

## Delete Entry

Edit mode, `editor.js` + `app.py`:
- "DELETE ENTRY" red button in the skip checkbox row (right-justified).
- Custom confirmation modal with "ARE YOU SURE YOU WANT TO DELETE THE [type] NAMED [title]?" message. Cancel button is focused by default.
- `POST /editor/delete` removes the entry from `bundledb.json` (and from `showcase-data.json` for sites).

## Delete Test Entries

- "DELETE ALL TEST ENTRIES" button appears next to DELETE ENTRY only when entries with "bobdemo99" in their title exist.
- `POST /editor/delete-test-entries` removes all matching entries from both `bundledb.json` and `showcase-data.json`.

## Test Data Guards

- When any type is selected, an orange warning banner appears below the type selector if any entries with "bobdemo99" in their title exist. Banner shows the count and a DELETE ALL TEST ITEMS button.
- **Run Latest guard**: Clicking Run Latest when test data is present shows a warning modal ("Test Data Present") with Cancel and Proceed buttons. Proceed is focused by default.
- **Deploy guard**: Clicking Deploy when test data is present shows a blocking modal ("UNABLE TO DEPLOY WHEN TEST DATA IS PRESENT") with DELETE TEST ITEMS and Close buttons. DELETE TEST ITEMS is focused by default.
- Banner and guards refresh after test entries are deleted. Banner hides on mode switch.

## Skip Checkbox

Edit mode only:
- A "Skip (exclude from site generation)" checkbox appears at the top of the edit form.
- When checked, adds `Skip: true` to the saved item.

## Description Extraction

`services/description.py`:
- `extract_description(url)` fetches a page and extracts the description using a multi-source fallback chain mirroring `dbtools/lib/getdescription.js`: meta description, Open Graph, Twitter Card, Dublin Core, Schema.org microdata, JSON-LD.
- Sanitizes output (removes HTML tags, control characters, zero-width characters; escapes ampersands/quotes; converts markdown links to HTML; truncates to 300 chars).
- YouTube URLs return "YouTube video" without fetching.
- Exposed via `POST /editor/description`.

## Fetch Buttons

Per-type, create and edit:
- **Blog posts**: "Fetch Description" button after Categories (hidden if description already populated in edit mode). Fetches blog post description from the Link URL.
- **Sites**: "Fetch Description, Favicon, Screenshot & Leaderboard" button after Date. Fetches all four in parallel from the Link URL. Shows "Refresh..." when all fields are already populated.
- **Releases**: "Fetch Description" button after Date. Shows "Refresh Description" when description is already populated.
- **Starters**: "Fetch Description & Screenshot" button after Demo. Fetches both from the Demo URL (not the GitHub link). Shows "Refresh..." when both fields are populated.
- All fetch buttons use a `lastFetchedUrl` guard to prevent redundant fetches; clicking the button resets this to allow re-fetching.

## Author Autocomplete

Blog post create:
- Author field uses a `<datalist>` populated from all unique authors in the database.
- Tab-completion auto-fills when there's exactly one fuzzy match.
- Selecting an existing author auto-fills empty fields (AuthorSite, AuthorSiteDescription, favicon, rssLink, socialLinks) from the most recent post by that author, and renames the author info button to "Refresh Author Info".

## Author Info Fetching

Blog posts, create and edit:
- AuthorSite auto-populates with the origin of the blog post Link URL when empty (e.g., `https://example.com/blog/post` -> `https://example.com`). Triggers both at form render time and when a new author name is entered (on Author field blur). Editable since the author's site may differ.
- "Fetch Author Info" button appears after AuthorSite for new authors (not in database).
- "Refresh Author Info" button appears for existing authors (after autocomplete populates fields).
- Both buttons call `POST /editor/author-info` with the AuthorSite URL, which fetches in parallel: AuthorSiteDescription (via description service), socialLinks (via social_links service), favicon (via favicon service), rssLink (via rss_link service).
- Only fills empty fields (won't overwrite existing values).

## RSS Link Discovery

`services/rss_link.py`:
- `extract_rss_link(url)` mirrors `dbtools/lib/getrsslink.js`: extracts origin, looks for `<link type="application/rss+xml">` or `<link type="application/atom+xml">` in the HTML head, then probes common feed paths (`/feed.xml`, `/rss.xml`, `/index.xml`, etc.).
- Validates probed paths by checking response content looks like a feed (not an HTML error page).

## Categories Checkbox Grid

Blog posts:
- Categories rendered as a 5-column checkbox grid using CSS `grid-auto-flow: column` with dynamic row count.
- Display aliases shorten long category names without affecting stored values: "Internationalization" -> "i18n", "Migrating to Eleventy" -> "Migrating to 11ty", "The 11ty Conference 2024" -> "11ty Conf 2024" (configured in `categoryDisplayNames` in `editor.js`).
- Includes an "Add new category" input + button for dynamically adding categories.
- Pre-checks categories that exist on the current item.

## Favicon Fetching

`services/favicon.py`:
- Tries existing file -> Google API (`s2/favicons`) -> HTML extraction (prioritizing SVG, large PNG, apple-touch-icon). Non-SVG/ICO images resized to 64x64 PNG via Pillow. Saves to `11tybundledb/favicons/` and copies to `_site/img/favicons/`.
- Exposed via `POST /editor/favicon`.

## Screenshot Capture

`scripts/capture-screenshot.js`:
- Puppeteer captures full-page JPEG at 1920x1080 with `networkidle0` + 3s delay. Saves to `11tybundledb/screenshots/` and `content/screenshots/`. Returns JSON with filename and path.
- `POST /editor/screenshot` runs the script via `subprocess.run()` with 60s timeout.
- `GET /editor/screenshot-preview/<filename>` serves captured screenshots for inline preview.

## Screenshot Data Separation

- `screenshotpath` is stored only in `showcase-data.json`, not in `bundledb.json`.
- `GET /editor/data` returns `{"bundledb": [...], "showcase": [...]}`. Site entries in `bundledb` have `screenshotpath` merged from `showcase-data.json` (matched by link). The `showcase` array is used client-side for duplicate link detection.
- On save (create or edit), `screenshotpath` is stripped from the item before writing to `bundledb.json` and written only to `showcase-data.json`.

## Leaderboard Link Check

`services/leaderboard.py`:
- `check_leaderboard_link(url)` probes `https://www.11ty.dev/speedlify/<normalized-domain>` to check if a site appears on the 11ty Speedlify Leaderboard.
- Normalizes hostname: strips `www.`, replaces `.` and `/` with `-`. Tries variations with/without `www-` prefix and trailing slash.
- Returns the leaderboard URL string if found (HTTP 200), or `None`.
- `POST /editor/leaderboard` endpoint.
- `leaderboardLink` is stored only in `showcase-data.json` (same pattern as `screenshotpath`).
- Fetched in parallel with favicon, screenshot, and description in the site fetch flow.

## Content Review

`services/content_review.py`:
- When adding a site, AI reviews the site's content for hateful, discriminatory, or extremist opinions using Claude Haiku via the `anthropic` SDK.
- Runs in parallel with favicon, screenshot, description, and leaderboard fetches as a 5th promise in `fetchSiteData()`.
- `fetch_page_text(url)` fetches a page and extracts visible body text (strips nav, header, footer, aside, script, style elements), truncated to ~3000 chars.
- `find_subpages(url, soup)` identifies /about, /author, /beliefs pages and up to 10 blog post title links from the homepage.
- `review_content(url)` fetches homepage + subpages, concatenates text, sends to Claude Haiku. Returns `{"flagged": bool, "confidence": str, "summary": str, "pages_checked": int, "pages": [...]}`.
- On any error (no API key, network failure, unparseable response), returns `{"flagged": false, "error": "..."}` -- the fetch flow continues normally.
- `POST /editor/content-review` endpoint.
- Results shown in a banner (`#content-review-banner`) between the test-data-banner and search section: green for clear, red for flagged.
- Banner has three buttons: **Details** (opens modal), **Cancel Entry** (clears banner, form, and type selection), **Dismiss** (hides banner only).
- Banner auto-scrolls to top of page when displayed.
- Requires `ANTHROPIC_API_KEY` env var in `.env`.

## Showcase Review

`services/showcase_review.py`:
- Bulk scanner that reviews all sites in `showcase-data.json` using `review_content()` from `content_review.py`.
- Run as CLI: `python -m services.showcase_review [--test | --full | --site=URL | --report-only]`.
- `--test`: reviews 10 randomly selected non-allowlisted sites. `--full`: reviews all remaining. `--site=URL`: single ad-hoc review (not saved). `--report-only`: regenerates HTML report from existing results.
- **Results file** (`showcase-review-results.json`): dict with `reviewed` mapping normalized URLs to `{title, flagged, confidence, summary, pages_checked, pages}` or `{title, error}`.
- **Allowlist** (`data/showcase-cleared-sites.json`): dict of normalized URLs -> `{cleared, title}`. Sites that pass review are automatically added. Allowlisted sites are skipped on subsequent runs.
- **HTML report** (`showcase-review-report.html`): generated via `generate_report()`, shows flagged sites and error sites.
- Review flags are surfaced in the editor: `/editor/data` includes a `review_flags` dict, and item cards show red "flagged" or orange "error" badges.
- Rate limit handling: retries up to 3 times with exponential backoff (30s, 60s, 120s).

## Site Save Side-Effects

- On create, site saves call `add_bwe_to_post(title, link)` to append the site to the BWE "TO BE POSTED" list, and prepend an entry to `showcase-data.json` with title, description, link, date, formattedDate, favicon, screenshotpath, and leaderboardLink.
- On edit, site saves sync the matching `showcase-data.json` entry (matched by link) with current title, description, favicon, screenshotpath, leaderboardLink, date, and formattedDate.
- Dates written to `showcase-data.json` are normalized to `YYYY-MM-DD` format (truncated from bundledb's full datetime via `[:10]`).

## Custom Field Labels

`fieldDisplayNames` and `fieldLabel()` in `editor.js`:
- `Link` shows as "GitHub repo link" for release/starter types.
- `Demo` shows as "Link to demo site" for starter type.
- CamelCase field names display with spaces: `formattedDate` -> "Formatted Date", `slugifiedAuthor` -> "Slugified Author", etc.

## Author-Field Propagation

Edit mode, `editor.js` + `app.py`:
- When saving a blog post edit, `buildPropagation()` compares original item (snapshotted as `originalItem` when the form opens) against edited values.
- Checks `PROPAGATABLE_FIELDS` (AuthorSiteDescription, rssLink, favicon) and `PROPAGATABLE_SOCIAL` (mastodon, bluesky, youtube, github, linkedin) for empty->non-empty transitions.
- If any newly-filled fields exist, scans `allData` for other blog posts by the same `Author` that also lack those fields.
- Shows a `confirm()` dialog with field names and affected post count.
- If confirmed, sends `propagate: [{index, field, value}, ...]` array in the save payload.
- Backend iterates `propagate` entries, handles both top-level fields and `socialLinks.*` sub-fields, writes once.
- Response includes `propagated` count; client syncs changes into local `allData` and shows status message.
