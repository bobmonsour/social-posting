# Socially Bundled

A personal publication management tool for [11tybundle.dev](https://11tybundle.dev). What started as a simple social media cross-poster has evolved into the primary editorial interface for managing the 11ty Bundle -- a curated database of blog posts, sites, releases, and starters from the Eleventy community.

The app has two main surfaces: a **Bundle Entry Editor** for creating, editing, and publishing database entries, and a **Social Posting** page for cross-posting to Mastodon, Bluesky, and Discord with workflow integrations that tie the two together.

> **Note**: This app is purpose-built for the sole use of the editor of 11tybundle.dev, running on a local machine with access to sibling project directories (`dbtools/`, `11tybundle.dev/`, etc.) and local Node.js tooling. It is not designed for general-purpose deployment. That said, the patterns and architecture here may be instructive for anyone looking to build their own editorial tooling or social media cross-posting workflows.

## Bundle Entry Editor

The editor (`/editor`) is the main workspace for managing `bundledb.json`, the database that powers 11tybundle.dev. It supports four entry types: blog posts, sites, releases, and starters.

**Creating entries**:
- Select a type and fill in fields with auto-populated date, issue number, and type.
- Title and Author fields auto-compute slugified versions on blur (matching `@sindresorhus/slugify`).
- Per-type fetch buttons pull descriptions, favicons, screenshots, and author info from the entry's URL.
- Author autocomplete from existing database entries, with auto-fill of author-level fields (site description, social links, favicon, RSS link).
- Duplicate link detection on blur and save, with `www.`/non-`www.` normalization.
- View JSON preview before saving (for sites, also shows the showcase-data entry).

**Editing entries**:
- Fuzzy search (Fuse.js) across type-specific fields to find entries.
- Author-field propagation: filling in a previously-empty author-level field prompts to update all other posts by the same author.
- Skip entries to exclude them from site generation.
- Delete entries with confirmation, or bulk-delete test entries.

**Build and deploy**:
- Save and run the local Eleventy dev server to preview changes.
- Deploy directly to production from the editor.
- End-session scripts generate issue records, insights, and latest-data files.

## Social Posting

Cross-post to Mastodon, Bluesky, and Discord from a single compose form.

- Compose once, publish to all three platforms simultaneously
- Attach up to 4 images (with required alt text) or a link card (mutually exclusive)
- Save drafts for later, retry failed posts
- Content warnings / content labels per platform (Discord uses spoiler syntax)
- Grapheme-aware character counting (500 for Mastodon, 300 for Bluesky, 2000 for Discord)
- Bluesky images auto-compressed to fit the 1MB limit
- Discord posts via webhook with auto-generated link previews
- Light and dark mode UI

### Modes

Modes pre-fill per-platform textareas with hashtags, mentions, and prefixes tailored to a topic.

- **11ty** -- Adds `#11ty` and platform-specific `@11ty` mentions as suffixes. Text syncs between platform textareas.
- **11ty BWE** -- "Built with Eleventy:" prefix with the same suffixes. Textareas are independently editable after initial population.

### Built with Eleventy Workflow

A markdown file (`built-with-eleventy.md`) tracks sites built with Eleventy. The sidebar shows a "Sites to Post" queue with per-platform M/B/D checkboxes (Mastodon/Bluesky/Discord) and a "Sites Posted" history with colored platform badges. Clicking **Post** on a queued site populates the compose form in 11ty BWE mode with the selected platforms. Each queued site also has a **Del** button (with confirmation modal) to remove it from the list.

Partial posting is supported: if only some platforms are selected and posted successfully, the site stays in the queue with the remaining platforms, while the posted platforms appear in the "Sites Posted" section. A second post merges with the existing entry.

When creating a new site entry in the editor, it is automatically added to the Sites to Post queue, connecting the editorial and social posting workflows.

### Social Link Tagging

When posting about a "Built with Eleventy" site, the app automatically fetches the site's HTML to discover the owner's Mastodon and Bluesky profiles (Discord does not support @-mentions via webhooks). Discovered @-mentions are appended to the per-platform textareas. Detection strategies include JSON-LD `sameAs` arrays, `rel="me"` links, and URL pattern matching across the homepage, `/about/`, and `/en/` pages.

## Tech Stack

- **Backend**: Flask, Mastodon.py, atproto, requests, Pillow, BeautifulSoup4, python-dotenv
- **Frontend**: Jinja2, Pico CSS (CDN), vanilla JS, Fuse.js (CDN, editor search)
- **Tooling**: Node.js + Puppeteer (screenshot capture)
- **Storage**: Flat JSON files for post history and bundle data, filesystem for images (no database)
