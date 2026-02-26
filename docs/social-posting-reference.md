# Social Posting Reference

Detailed reference for the social posting page (compose/post), modes, social link tagging, failed posts, and BWE sites-to-post management. See CLAUDE.md for a summary.

## Modes

Modes switch the UI from a single shared textarea to per-platform textareas, each pre-populated with platform-specific hashtags and mentions. Configured in `modes.py`.

Current modes:
- **11ty**: Adds `#11ty @11ty@neighborhood.11ty.dev` (Mastodon) and `@11ty.dev` (Bluesky) as suffixes. Cursor at start.
- **11ty Bundle Issue**: Same suffixes as 11ty, with `11ty Bundle Issue {issue_number}` prefix (dynamically resolved with the latest issue number from bundledb). Cursor placed after the prefix. Uses `{issue_number}` placeholder in `modes.py`, resolved via `_resolve_modes()` in `app.py`.
- **11ty BWE**: Same suffixes as 11ty, but with `Built with Eleventy: ` prefix. Cursor placed after the prefix.

Mode behavior:
- Selecting a mode auto-checks and locks the mode's platform checkboxes (currently Mastodon and Bluesky; Discord Showcase and Discord Content are not auto-selected by any mode).
- Per-platform textareas appear with prefix+suffix pre-filled.
- Switching between modes (including None) resets all textareas to their initial state -- user text is not carried over.
- "Mirror across platforms" checkbox (default unchecked) enables cross-sync: typing in one platform textarea mirrors the body (preserving per-platform prefix/suffix) to the other. Checkbox is shown only when a mode is active and resets to unchecked on every mode switch.
- "Show Preview" button renders all platforms with highlighted @mentions, #hashtags, and URLs.
- Modes are stored on drafts/history entries as `mode` and `platform_texts` fields (backward compatible -- absent for non-mode posts).

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
- Checks homepage, `/about/`, `/en/` -- stops early after `/about/` if links found.
- URL-to-mention conversion: `https://instance.social/@user` -> `@user@instance.social`; `https://bsky.app/profile/handle` -> `@handle`.
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

## BWE Sites to Post Management

The compose page sidebar shows "Sites to Post" from `built-with-eleventy.md`. Each entry has:
- **M/B/D/C checkboxes**: per-platform selection (Mastodon/Bluesky/Discord Showcase/Discord Content). All unchecked by default. Clicking **Post** reads these checkboxes to set the main platform checkboxes and activate 11ty-bwe mode.
- **Post** button (or **Use** link if a draft exists): populates the compose form in 11ty-bwe mode with the selected platforms.
- **Del** button: removes the entry from the TO BE POSTED list via `POST /bwe-to-post/delete`. Shows a confirmation modal with Cancel focused by default.

**Per-platform tracking** (`services/bwe_list.py`):
- `ALL_PLATFORMS = ["B", "C", "D", "M"]`, `DEFAULT_PLATFORMS = []` (all unchecked). `C` = Discord Content channel.
- Markdown format uses optional `{PLATFORMS}` suffix: `[Name](url) {M,B}` or `[Name](url) {D}` or `[Name](url) {C}`. No suffix = default (empty).
- Posted entries: `2026-02-21 [Name](url) {M,B}`. Legacy `-- status` format parsed for backward compat via `_extract_platforms_from_status()`.
- `_write_bwe_file(to_post, posted)` consolidates all file-writing (previously duplicated 5x).
- `update_bwe_after_post(name, url, posted_platforms, timestamp)`: partial posting support -- remaining platforms stay in to_post, posted platforms merge with existing posted entry if present.
- `mark_bwe_posted()` retained as legacy wrapper calling `update_bwe_after_post()`.

**Sites Posted** sidebar shows colored platform badges (M=purple, B=blue, D=blurple, C=teal) for each posted entry.
