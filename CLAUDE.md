# Social Posting

Personal social media cross-poster. Single Flask app that posts to Mastodon and Bluesky from one form.

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
│   └── bluesky_client.py   # Bluesky AT Protocol via atproto
├── services/
│   ├── media.py            # process_uploads, cleanup_uploads, compress_for_bluesky
│   ├── link_card.py        # Open Graph metadata fetching
│   ├── social_links.py     # Extract Mastodon/Bluesky profiles from site HTML
│   └── favicon.py          # Multi-strategy favicon fetching (existing/Google API/HTML extraction)
├── scripts/
│   └── capture-screenshot.js  # Puppeteer full-page screenshot capture
├── templates/              # Jinja2 (base.html, compose.html, result.html)
├── static/
│   ├── css/style.css       # Pico CSS overrides, warm color scheme, light/dark
│   └── js/compose.js       # Form interactivity, modes, draft/image handling, validation
├── posts/
│   ├── history.json        # All posts, drafts, and failed posts (newest first)
│   └── draft_images/       # Persisted images keyed by draft/failed UUID
├── uploads/                # Temporary upload dir (cleaned after posting)
└── docs/
    ├── modes.md            # Requirements doc for modes feature
    └── tagging-site-owners.md  # Requirements doc for social link tagging
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
- Selecting a mode auto-checks and locks both platform checkboxes.
- Per-platform textareas appear with prefix+suffix pre-filled.
- Text typed in one platform textarea is synced to the other (body only; prefix/suffix preserved per-platform).
- Switching between modes strips old prefix/suffix and applies new ones, preserving user text.
- "Show Preview" button renders both platforms with highlighted @mentions, #hashtags, and URLs.
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

The `/editor` page provides search and edit for `bundledb.json` items, plus a create mode for adding new entries. Mode (Edit/Create) is selected via radio buttons at the top, then type is selected. In edit mode, fuzzy search (Fuse.js) over type-specific keys finds items. In create mode, selecting a type opens a blank form with auto-populated fields. Fields are ordered per `FIELD_ORDER` in `editor.js`. Saves go to `POST /editor/save`, which creates a backup on first save per session.

**Edit/Create modes** (`editor.js` + `editor.html`):
- Mode radio buttons (Edit/Create) at top of editor. Edit mode is the default.
- Create mode hides search/recent items and shows a blank form for the selected type.
- New items are auto-populated with `Date` (ISO), `formattedDate` (human-readable), `Issue` (current max from data), and `Type`.
- Create saves append to the end of the `bundledb.json` array (edit saves update in place).

**Skip checkbox** (edit mode only):
- A "Skip (exclude from site generation)" checkbox appears at the top of the edit form.
- When checked, adds `Skip: true` to the saved item.

**Author autocomplete** (blog post create):
- Author field uses a `<datalist>` populated from all unique authors in the database.
- Tab-completion auto-fills when there's exactly one fuzzy match.
- Selecting an author auto-fills empty fields (AuthorSite, AuthorSiteDescription, favicon, rssLink, socialLinks) from the most recent post by that author.

**Categories checkbox grid** (blog posts):
- Categories rendered as a checkbox grid instead of a comma-separated text input.
- Includes an "Add new category" input + button for dynamically adding categories.
- Pre-checks categories that exist on the current item.

**Favicon & screenshot fetching** (site creates):
- A "Fetch Favicon & Screenshot" button appears after the Link field in site create forms.
- Fires `POST /editor/favicon` and `POST /editor/screenshot` in parallel.
- Favicon service (`services/favicon.py`): tries existing file → Google API (`s2/favicons`) → HTML extraction (prioritizing SVG, large PNG, apple-touch-icon). Non-SVG/ICO images resized to 64x64 PNG via Pillow. Saves to `dbtools/lib/favicons/` and copies to `_site/img/favicons/`.
- Screenshot script (`scripts/capture-screenshot.js`): Puppeteer captures full-page JPEG at 1920x1080 with `networkidle0` + 3s delay. Saves to `dbtools/screenshots/` and `content/screenshots/`. Returns JSON with filename and path.
- `POST /editor/screenshot` runs the script via `subprocess.run()` with 60s timeout.
- `GET /editor/screenshot-preview/<filename>` serves captured screenshots for inline preview.

**Site create side-effects**:
- On save, site creates automatically call `add_bwe_to_post(title, link)` to append the site to the BWE "TO BE POSTED" list.
- A new entry is prepended to `showcase-data.json` with title, description, link, date, formattedDate, favicon, and screenshotpath.

**Custom field labels**:
- `Link` shows as "GitHub repo link" for release/starter types.
- `Demo` shows as "Link to demo site" for starter type.

**Author-field propagation** (edit mode, `editor.js` + `app.py`):
- When saving a blog post edit, `buildPropagation()` compares original item (snapshotted as `originalItem` when the form opens) against edited values.
- Checks `PROPAGATABLE_FIELDS` (AuthorSiteDescription, rssLink, favicon) and `PROPAGATABLE_SOCIAL` (mastodon, bluesky, youtube, github, linkedin) for empty→non-empty transitions.
- If any newly-filled fields exist, scans `allData` for other blog posts by the same `Author` that also lack those fields.
- Shows a `confirm()` dialog with field names and affected post count.
- If confirmed, sends `propagate: [{index, field, value}, ...]` array in the save payload.
- Backend iterates `propagate` entries, handles both top-level fields and `socialLinks.*` sub-fields, writes once.
- Response includes `propagated` count; client syncs changes into local `allData` and shows status message.

## Key Conventions

- All paths in `app.py` are `__file__`-relative via `_BASE_DIR` (not CWD-relative).
- `config.py` uses `__file__`-relative path for `UPLOAD_FOLDER`.
- Image file inputs: the `<input type="file">` in the template has **no `name` attribute** — files are submitted via a dynamically-created hidden input in the JS submit handler. This prevents an empty file part from misaligning alt text indices in `process_uploads`.
- Alt text is required for all images (enforced client-side on submit).
- Bluesky images auto-compressed to fit 1MB limit.
- Character counting is grapheme-aware (`Intl.Segmenter`).
- Content warnings use radio buttons for both platforms (None, Sexual, Nudity, Graphic Media, Porn, Political). Mastodon values are human-readable strings used as spoiler text; Bluesky values are API label identifiers.
- Draft deletion route (`/draft/<id>/delete`) handles drafts, failed posts, and legacy failed entries.
- Sidebar post cards show badges (DRAFT/FAILED/platform), action buttons, 50-char text preview, and timestamp.

## Configuration

Environment variables in `.env` (see `.env.example`):

- `MASTODON_INSTANCE_URL` / `MASTODON_ACCESS_TOKEN` (token needs `write:statuses` and `write:media` scopes)
- `BLUESKY_IDENTIFIER` / `BLUESKY_APP_PASSWORD`

## Tech Stack

- **Backend**: Flask, Mastodon.py, atproto, Pillow, BeautifulSoup4, python-dotenv
- **Frontend**: Jinja2, Pico CSS (CDN), vanilla JS, Fuse.js (CDN, editor search)
- **Tooling**: Node.js + Puppeteer (screenshot capture)
- **No database** — flat JSON file for history, filesystem for images
