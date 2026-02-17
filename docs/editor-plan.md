# Plan: bundledb.json Editor Page

## Context

The 11ty Bundle website is backed by a ~2,600-item JSON database (`bundledb.json`). Currently, editing items requires using the Node.js `make-bundle-entries.js` CLI tool. This plan adds a browser-based editor page to the social-posting Flask app, providing a searchable, form-based interface for finding and editing existing items.

## Decisions Captured

- **Initial list**: Show 5 most recently dated items when a Type is selected; search spans all items of that type
- **Computed fields**: All fields shown as editable inputs (including slugifiedTitle, formattedDate, etc.)
- **Scope**: Edit existing items only (structure to allow adding new items later)
- **Backup**: Mirror the `makeBackupFile` pattern from dbtools — copy to `bundledb-backups/` with timestamped filename, one backup per session

## Files to Modify

1. **`templates/base.html`** — Add "Edit bundledb.json" button in `.site-header`
2. **`app.py`** — Add routes: `GET /editor`, `GET /editor/data`, `POST /editor/save`
3. **`static/css/style.css`** — Add header-actions layout + editor-specific styles

## Files to Create

4. **`templates/editor.html`** — Editor page extending base.html
5. **`static/js/editor.js`** — Client-side search, form generation, save/cancel logic

## Implementation

### 1. Navigation button (`base.html`)

Wrap the h1 and theme-toggle in a `.header-actions` div. Add an `<a href="/editor">` button styled to match existing button conventions (uppercase, bold, letter-spacing). The compose page should also get a corresponding link back.

### 2. Flask routes (`app.py`)

Add constants:
```python
BUNDLEDB_PATH = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/bundledb.json"
BUNDLEDB_BACKUP_DIR = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/bundledb-backups"
```

**`GET /editor`** — renders `editor.html`

**`GET /editor/data`** — returns full bundledb.json as JSON (client does all filtering/search)

**`POST /editor/save`** — accepts `{index, item, backup_created}`:
- If `backup_created` is false, copy bundledb.json to `bundledb-backups/bundledb-YYYY-MM-DD--HHMMSS.json` (matching the pattern in `dbtools/lib/utils.js:53-78`)
- Replace the item at `index` in the array
- Write updated JSON back to file
- Return `{success, backup_created}`

### 3. Editor template (`editor.html`)

Layout:
- **Type selector**: Radio buttons for blog post / site / release / starter
- **Recent items**: Shows 5 most recent items of selected type (by Date, descending)
- **Search input**: Fuzzy search across all items of selected type
- **Search results**: List of matching item titles (clickable)
- **Edit form**: Dynamically generated fields for the selected item (hidden until an item is clicked)
- **Save / Cancel buttons**: Save writes to backend; Cancel returns to search view

Include Fuse.js via CDN for fuzzy search.

### 4. Editor JS (`editor.js`)

**Data flow:**
1. On page load, fetch `/editor/data` → store full array in `allData`
2. On type change, filter `allData` by Type, show 5 most recent by Date, reinitialize Fuse.js
3. On search input, run Fuse.js query against all items of current type
4. On item click, dynamically generate form fields based on item type

**Search keys by type:**
- Blog post: Title, Author
- Site / Release / Starter: Title

**Form generation by type — field order:**

| Blog Post | Site | Release | Starter |
|-----------|------|---------|---------|
| Issue | Issue | Issue | Issue |
| Type | Type | Type | Type |
| Title | Title | Title | Title |
| slugifiedTitle | description | description | Link |
| Link | Link | Link | Demo |
| Date | Date | Date | description |
| formattedDate | formattedDate | formattedDate | screenshotpath |
| description | favicon | | |
| Author | | | |
| slugifiedAuthor | | | |
| AuthorSite | | | |
| AuthorSiteDescription | | | |
| socialLinks.* (5 sub-fields) | | | |
| favicon | | | |
| rssLink | | | |
| Categories (comma-separated) | | | |

**Special field handling:**
- `socialLinks`: Render as a nested fieldset with 5 text inputs (mastodon, bluesky, youtube, github, linkedin)
- `Categories`: Render as a single text input; split on comma for save, join on comma for display
- `description`: Use `<textarea>` instead of `<input>` (descriptions can be long)

**Save flow:**
1. Collect form values, rebuild item object (reassemble socialLinks object, split Categories)
2. POST to `/editor/save` with index, rebuilt item, and `backupCreated` flag
3. On success, update `allData[index]` locally, set `backupCreated = true`, return to search view

**Session backup flag:** `backupCreated` starts false, set to true after first successful save. Sent with each save request so the server knows whether to create a backup.

### 5. CSS additions (`style.css`)

- `.header-actions`: flex container for the nav button + theme toggle
- `.editor-container`: max-width ~900px, centered
- `.item-list` / `.item-card`: clickable cards for search results (border, hover highlight)
- `.form-field`: label + input pairs with uppercase labels matching existing legend style
- `.nested-fieldset`: for socialLinks group
- `.edit-actions`: flex row for Save/Cancel buttons

## Verification

1. Run `python app.py` and navigate to `127.0.0.1:5555`
2. Confirm "Edit bundledb.json" button appears next to title and navigates to `/editor`
3. On editor page, confirm all 4 type radios work and show 5 most recent items each
4. Type a fuzzy search term (e.g. "elev") and confirm results appear across all items of the type
5. Click a result, confirm all fields appear in the edit form with correct values
6. Edit a field, click Save, confirm:
   - A backup file appears in `bundledb-backups/` with timestamped name
   - The change is written to `bundledb.json`
   - A second save in the same session does NOT create another backup
7. Click Cancel on an edit and confirm return to search view without changes
