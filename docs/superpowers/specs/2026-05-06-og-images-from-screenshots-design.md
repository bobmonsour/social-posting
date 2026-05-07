# OG image generation from screenshots — design

## Background

The 11ty Bundle showcase captures full-page screenshots of each showcased site at 1920×1080 (`<domain>-large.jpg`). When a Showcase detail page is shared on social media, the platform pulls the page's Open Graph image — and at 1920×1080 the screenshot crops poorly in a 1.91:1 OG card.

This design adds a second derived image, `<domain>-og.jpg`, sized to the standard OG ratio of 1200×630, generated alongside the existing screenshot.

The Eleventy site changes (updating Showcase detail page meta tags to point at the OG image) are out of scope here and will be handled as a separate effort.

## Decisions

| Decision | Choice |
|---|---|
| Output format | JPEG (`.jpg`) |
| Output dimensions | 1200×630 |
| Resize strategy | Resize to 1200 wide (preserves aspect, yields 1200×675), extract top 1200×630 |
| JPEG quality | 90 |
| Image processing tool | Sharp, in Node |
| Where in the pipeline | `scripts/capture-screenshot.js` (modified) + `scripts/backfill-og-images.js` (new) |
| Storage | `11tybundledb/og-images/<domain>-og.jpg` and `11tybundle.dev/content/og-images/<domain>-og.jpg` |
| Per-capture behavior | Always regenerate the OG when the screenshot is captured |
| Backfill behavior | Idempotent — skip if OG already exists; safe to re-run |

## Architecture

Extend the existing Node screenshot pipeline to produce a second derived image alongside `<domain>-large.jpg`. After Puppeteer writes the full-page capture, a Sharp post-processing step resizes it to 1200 wide (yielding 1200×675), then crops the top 1200×630 region (trimming 45px from the bottom), and saves as `<domain>-og.jpg` at quality 90 — written to both `11tybundledb/og-images/` and `11tybundle.dev/content/og-images/`. A separate one-shot CLI script handles the ~1590 existing screenshots using the same pipeline. No Python or `app.py` changes are required for this scope.

## Components

### 1. `scripts/lib/og-from-screenshot.js` (new)

Shared helper module. Single exported function:

```js
async function generateOg(sourcePath, destPaths) { ... }
```

Where `destPaths` is `[bundledbPath, contentPath]`. Encapsulates:

- Sharp pipeline: `sharp(sourcePath).resize({ width: 1200 }).extract({ left: 0, top: 0, width: 1200, height: 630 }).jpeg({ quality: 90 })`
- `mkdir -p` on each destination directory
- Writing the same buffer to both destinations

Both `capture-screenshot.js` and `backfill-og-images.js` import it.

### 2. `scripts/capture-screenshot.js` (modified)

After the existing Puppeteer screenshot write:

- Compute `og-images/<domain>-og.jpg` paths for both bundledb and content trees
- Call `generateOg(largeJpgPath, [bundledbOgPath, contentOgPath])`
- Always regenerate, even if the OG file already exists
- Output JSON gains an `ogpath: "/og-images/<domain>-og.jpg"` field for future callers; existing fields (`success`, `filename`, `screenshotpath`) unchanged

### 3. `scripts/backfill-og-images.js` (new)

One-shot CLI. Run as `node scripts/backfill-og-images.js` from project root.

- Enumerates `11tybundledb/screenshots/*-large.jpg`
- For each, derives `<domain>-og.jpg`
- **Skips** if `11tybundledb/og-images/<domain>-og.jpg` already exists (idempotent)
- Otherwise calls `generateOg()` with the same dest paths as the capture script
- Logs `[N/total] <domain> -> created | skipped | error: <msg>` per file
- Per-file errors are logged to stderr but do NOT abort the run
- Final summary line: `Done. created: X, skipped: Y, errors: Z`
- Exit code 0 if no errors, 1 otherwise

To force a full regeneration: delete `11tybundledb/og-images/` and re-run.

### 4. `package.json` (modified)

Add `"sharp": "^0.33"` (latest stable major) to `dependencies`.

## Data flow

### Per-capture (editor's Capture button)

1. User clicks Capture in the editor
2. `app.py` shells out: `node scripts/capture-screenshot.js <url>`
3. Puppeteer captures 1920×1080 → writes `<domain>-large.jpg` to `11tybundledb/screenshots/` and `11tybundle.dev/content/screenshots/` (existing behavior)
4. **NEW:** `generateOg()` reads the just-written large file, runs the Sharp pipeline, writes `<domain>-og.jpg` to both og-images destinations
5. Script returns `{ success: true, filename, screenshotpath, ogpath }`
6. Editor displays the screenshot preview as it does today (no UI changes)

### Backfill (manual one-shot)

1. User runs `node scripts/backfill-og-images.js`
2. Script processes each `*-large.jpg` in `11tybundledb/screenshots/`, calling `generateOg()`
3. Progress logged per file; final summary printed; exit code reflects success

## Error handling

| Failure | Behavior |
|---|---|
| Puppeteer fails in capture script | Existing behavior: `{ success: false, error }` |
| OG generation fails after a successful screenshot | `{ success: false, error: "OG generation failed: <msg>" }`. The editor surfaces a clear error so the user can retry. Rationale: "always regenerate" means a missing/stale OG is a real failure, not something to silently swallow. |
| OG generation fails for a single file in backfill | Logged to stderr, increment error count, continue with remaining files. Process all 1590 even if a few fail. |
| Source screenshot has unexpected dimensions (not 1920×1080) | Let Sharp's `extract` fail loudly. All current screenshots are 1920×1080; defensive handling for hypothetical future formats is YAGNI. |
| Destination directory doesn't exist | `mkdir -p` inside `generateOg()` handles this. |

## Testing

Existing Node scripts in this project don't have automated tests — they're verified by running them. Following the same convention.

**Manual verification after implementation:**

1. Run capture on a single known URL via the editor's Capture button → verify `-large.jpg` and `-og.jpg` both land in both directories with correct dimensions
2. Open a few generated `-og.jpg` files and confirm framing (top-anchored, 1200×630, content not weirdly cropped)
3. Run backfill against a temp directory containing 5–10 sample screenshots, spot-check results
4. Run backfill on the full ~1590-screenshot set; confirm summary counts add up
5. Re-run backfill; verify all files report `skipped` (idempotency check)

## Out of scope

- Eleventy site updates (meta tags on Showcase detail pages pointing at OG images) — separate effort per the original doc
- `prebuild_sync.py` changes — not needed since capture/backfill write directly to both destinations
- Python service wrapper around the Node pipeline — Node is self-sufficient here
- A db-mgmt UI button for backfill — one-shot CLI is sufficient for a single run
- Per-type OG images (sites only here; starters/blog posts would be a separate decision)
