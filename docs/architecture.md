# Architecture

## Startup

When run directly, `app.py` creates the necessary directories (`uploads/`, `posts/`, `posts/draft_images/`) and starts Flask on `127.0.0.1:5555` in debug mode.

## History Layer

All state lives in a single JSON file (`posts/history.json`). Two helpers read/write the full list, and `save_post()` builds a new entry dict and prepends it (newest first). Every entry gets a UUID, timestamp, text, platform results, and optional fields for images, link URLs, modes, and draft/failed flags.

## Routes

### `GET /` — `compose()`

Renders the compose form. Passes in which platforms have credentials configured, the 10 most recent history entries (for the sidebar), and the available modes.

### `POST /post` — `post()`

The main workhorse. It forks into two paths:

1. **Draft path**: If `is_draft` is checked, it processes any uploaded images, copies them to `posts/draft_images/<new-uuid>/`, carries over images from a previous draft if re-saving, writes the entry to history with `is_draft: True`, and redirects back to compose. No API calls.

2. **Post path**: Validates platform selection, processes uploaded images (and any carried-over draft images), fetches Open Graph metadata for link cards if no images are attached, then loops through each selected platform:
   - Gets the platform client via the factory
   - Validates credentials
   - Compresses images for Bluesky if needed
   - Resolves per-platform text (mode support) or falls back to the shared text
   - Appends the link URL to Mastodon text (Mastodon doesn't support card embeds)
   - Calls `client.post()` and collects results

   After posting, if any platform failed and there were images, it persists the images and saves a failed entry for retry. On full success, it cleans up temp files and saves to history.

### `GET /draft/<id>` — `use_draft()`

Loads a draft back into the compose form for editing. Removes it from history so it doesn't appear as both a sidebar entry and form content.

### `GET /retry/<id>` — `retry_post()`

Same pattern as drafts but for failed posts. Matches entries with `is_failed: True` or the legacy detection (non-draft with empty platforms list).

### `POST /draft/<id>/delete` and `POST /post/<id>/delete`

Both route to `_delete_entry()`, which removes the entry from history and cleans up any persisted images on disk.

### `POST /link-preview`

AJAX endpoint — takes a URL, fetches its Open Graph metadata, returns title/description/image as JSON for the compose form preview.

## Key Design Patterns

- **Images have two lifetimes**: temporary in `uploads/` during a post attempt, and persistent in `posts/draft_images/<uuid>/` for drafts and failed posts. The `draft_image_data` hidden form field carries image metadata across re-saves.
- **Modes** change the text flow — instead of one shared `text` field, each platform gets its own text with platform-specific prefixes/suffixes. The `platform_texts` dict is stored on the history entry.
- **Platform differences are handled inline**: Bluesky gets image compression, Mastodon gets the link URL appended to text (since it doesn't embed cards via API), and content warnings use different form fields per platform.

## Lines of Code

About 2,460 lines across all source files:

- **CSS** — 593 lines (style.css)
- **JS** — 591 lines (compose.js)
- **Python** — 1,072 lines (app.py is the largest at 452)
- **Templates** — 280 lines (compose.html is the largest at 204)
