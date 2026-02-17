# Social Posting

A personal social media cross-poster. Post to Mastodon and Bluesky from a single form.

## What It Does

- Compose a post once, publish to Mastodon and Bluesky simultaneously
- Attach up to 4 images (with required alt text) or a link card (mutually exclusive)
- Save drafts for later, retry failed posts
- Content warnings / content labels per platform
- Grapheme-aware character counting (500 for Mastodon, 300 for Bluesky)
- Bluesky images auto-compressed to fit the 1MB limit
- Light and dark mode UI

## Modes

Modes pre-fill per-platform textareas with hashtags, mentions, and prefixes tailored to a topic. Text typed in one platform's textarea syncs to the other.

Current modes:
- **11ty** -- Adds `#11ty` and platform-specific `@11ty` mentions as suffixes
- **11ty BWE** -- "Built with Eleventy:" prefix with the same suffixes

## Built with Eleventy List

A markdown file (`built-with-eleventy.md`) tracks sites built with Eleventy. The sidebar shows a "Sites to Post" queue and a "Sites Posted" history. Clicking **Post** on a queued site populates the compose form in 11ty BWE mode. After posting, the site moves to the "Already Posted" section of the file with a timestamp and per-platform success/failure status.

## Social Link Tagging

When posting about a "Built with Eleventy" site, the app automatically fetches the site's HTML to discover the owner's Mastodon and Bluesky profiles. Discovered @-mentions are appended to the per-platform textareas. Detection strategies include JSON-LD `sameAs` arrays, `rel="me"` links, and URL pattern matching. The app checks the homepage, `/about/`, and `/en/` pages. Social links are fetched both when clicking **Post** on a queued site and when loading a saved BWE draft via **Use**.

## Bundledb Editor

The app includes an editor page (`/editor`) for the bundledb.json database that powers 11tybundle.dev. Search by item type (blog post, site, release, starter) with fuzzy matching, then edit any item's properties in a form.

**Author-field propagation**: When editing a blog post, if you fill in a previously-empty author-level field (AuthorSiteDescription, rssLink, favicon, or any socialLinks sub-field), the editor checks whether other blog posts by the same author are also missing that field. If so, it prompts you to update them all at once in a single save.

## Setup

1. Clone the repo and create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in your credentials:
   - `MASTODON_INSTANCE_URL` / `MASTODON_ACCESS_TOKEN` (needs `write:statuses` and `write:media` scopes)
   - `BLUESKY_IDENTIFIER` / `BLUESKY_APP_PASSWORD`

3. Run the app:
   ```bash
   python app.py
   ```
   The app runs at `http://127.0.0.1:5555`.

## Tech Stack

- **Backend**: Flask, Mastodon.py, atproto, Pillow, BeautifulSoup4, python-dotenv
- **Frontend**: Jinja2, Pico CSS (CDN), vanilla JS
- **Storage**: Flat JSON file for post history, filesystem for images (no database)
