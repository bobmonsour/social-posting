# OG Image Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate 1200×630 `-og.jpg` images alongside the existing 1920×1080 `-large.jpg` screenshots, both for new captures (in the editor) and as a one-shot backfill of the ~1590 existing screenshots.

**Architecture:** Add a shared Node helper (`scripts/lib/og-from-screenshot.js`) that uses Sharp to resize a screenshot to 1200 wide and crop the top 1200×630, writing the result to both `11tybundledb/og-images/` and `11tybundle.dev/content/og-images/`. Modify `scripts/capture-screenshot.js` to call the helper after each capture (always regenerate). Add `scripts/backfill-og-images.js` to process existing screenshots idempotently.

**Tech Stack:** Node.js, Puppeteer (already used), Sharp (new dep, JPEG resize/crop), CommonJS modules (matches the rest of `scripts/`).

**Spec reference:** `docs/superpowers/specs/2026-05-06-og-images-from-screenshots-design.md`

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `package.json` | Modify | Add `sharp` dependency |
| `scripts/lib/og-from-screenshot.js` | Create | Shared `generateOg(sourcePath, destPaths)` helper — Sharp pipeline + dual-write with mkdir |
| `scripts/capture-screenshot.js` | Modify | Call `generateOg()` after Puppeteer write; include `ogpath` in JSON output |
| `scripts/backfill-og-images.js` | Create | One-shot CLI; iterates `*-large.jpg`, skips existing OGs, calls `generateOg()` per file |

---

## Task 1: Add Sharp dependency

**Files:**
- Modify: `package.json`

- [ ] **Step 1: Install sharp and save to package.json**

Run:
```bash
cd /Users/Bob/Dropbox/Docs/Sites/social-posting && npm install sharp@^0.33
```

Expected: `package.json` gains `"sharp": "^0.33.x"` under `dependencies`; `package-lock.json` updated; `node_modules/sharp/` exists.

- [ ] **Step 2: Verify sharp loads**

Run:
```bash
cd /Users/Bob/Dropbox/Docs/Sites/social-posting && node -e "console.log(require('sharp').versions)"
```

Expected: prints a version object (e.g. `{ vips: '8.x.x', sharp: '0.33.x', ... }`) with no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/Bob/Dropbox/Docs/Sites/social-posting && git add package.json package-lock.json && git commit -m "Add sharp dependency for OG image generation" && git push origin main
```

---

## Task 2: Create the shared OG-generation helper

**Files:**
- Create: `scripts/lib/og-from-screenshot.js`

This is a pure function module. No tests are added — it's exercised end-to-end by Task 3 (manual capture verification) and Task 4 (backfill spot-check), matching the existing convention for Node scripts in this project (no Node test framework configured).

- [ ] **Step 1: Write the helper module**

Create `scripts/lib/og-from-screenshot.js` with:

```js
"use strict";

const fs = require("fs");
const path = require("path");
const sharp = require("sharp");

/**
 * Generate a 1200x630 OG image from a captured screenshot.
 *
 * Pipeline: resize to 1200 wide (preserves aspect; for a 1920x1080
 * source this yields 1200x675), then extract the top 1200x630 region
 * (trimming 45px from the bottom). Saved as JPEG quality 90.
 *
 * Writes the SAME buffer to every path in destPaths, creating parent
 * directories as needed.
 *
 * @param {string} sourcePath - Path to the source -large.jpg screenshot
 * @param {string[]} destPaths - One or more destination -og.jpg paths
 * @returns {Promise<void>}
 */
async function generateOg(sourcePath, destPaths) {
  const buffer = await sharp(sourcePath)
    .resize({ width: 1200 })
    .extract({ left: 0, top: 0, width: 1200, height: 630 })
    .jpeg({ quality: 90 })
    .toBuffer();

  for (const dest of destPaths) {
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.writeFileSync(dest, buffer);
  }
}

module.exports = { generateOg };
```

- [ ] **Step 2: Smoke-test the helper against a real screenshot**

Pick any existing screenshot to verify the pipeline works end-to-end before wiring it into capture-screenshot.js. Run:

```bash
cd /Users/Bob/Dropbox/Docs/Sites/social-posting && node -e "
const { generateOg } = require('./scripts/lib/og-from-screenshot');
const src = '/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/screenshots/11ty-rocks-large.jpg';
const dest = '/tmp/og-smoke-test.jpg';
generateOg(src, [dest]).then(() => {
  const { execSync } = require('child_process');
  console.log(execSync('sips -g pixelWidth -g pixelHeight ' + dest).toString());
}).catch(e => { console.error(e); process.exit(1); });
"
```

Expected output includes `pixelWidth: 1200` and `pixelHeight: 630`. File `/tmp/og-smoke-test.jpg` exists. No errors.

- [ ] **Step 3: Clean up smoke-test artifact**

Run:
```bash
rm /tmp/og-smoke-test.jpg
```

- [ ] **Step 4: Commit**

```bash
cd /Users/Bob/Dropbox/Docs/Sites/social-posting && git add scripts/lib/og-from-screenshot.js && git commit -m "Add OG image generation helper using Sharp" && git push origin main
```

---

## Task 3: Wire OG generation into capture-screenshot.js

**Files:**
- Modify: `scripts/capture-screenshot.js`

Per the spec, OG generation always runs when a screenshot is captured. If OG generation fails after the screenshot succeeded, the script returns `{success: false, error: "OG generation failed: ..."}` so the editor surfaces the failure.

- [ ] **Step 1: Add OG directory constants and helper import**

Modify `scripts/capture-screenshot.js`. After the existing `CONTENT_SCREENSHOTS_DIR` constant (line 18-19), add:

```js
const OG_IMAGES_DIR = path.join(BUNDLEDB_DIR, "og-images");
const CONTENT_OG_IMAGES_DIR =
  "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundle.dev/content/og-images";

const { generateOg } = require("./lib/og-from-screenshot");
```

- [ ] **Step 2: Generate the OG image after the screenshot is written**

In the `try` block of `main()`, immediately after the `fs.copyFileSync(dbtoolsPath, contentPath);` line that ends the screenshot copy (currently around line 60-61), add the OG generation block before the `console.log(JSON.stringify({ success: true, ... }))` call.

Replace:

```js
    // Copy to content directory
    const contentPath = path.join(CONTENT_SCREENSHOTS_DIR, filename);
    fs.copyFileSync(dbtoolsPath, contentPath);

    console.log(
      JSON.stringify({ success: true, filename, screenshotpath })
    );
```

With:

```js
    // Copy to content directory
    const contentPath = path.join(CONTENT_SCREENSHOTS_DIR, filename);
    fs.copyFileSync(dbtoolsPath, contentPath);

    // Generate OG image (1200x630) alongside the -large.jpg
    const ogFilename = `${domain}-og.jpg`;
    const ogpath = `/og-images/${ogFilename}`;
    try {
      await generateOg(dbtoolsPath, [
        path.join(OG_IMAGES_DIR, ogFilename),
        path.join(CONTENT_OG_IMAGES_DIR, ogFilename),
      ]);
    } catch (ogErr) {
      console.log(
        JSON.stringify({
          success: false,
          error: `OG generation failed: ${ogErr.message}`,
        })
      );
      process.exit(1);
    }

    console.log(
      JSON.stringify({ success: true, filename, screenshotpath, ogpath })
    );
```

- [ ] **Step 3: Manually verify capture end-to-end via the running app**

Start the app:
```bash
cd /Users/Bob/Dropbox/Docs/Sites/social-posting && source .venv/bin/activate && python app.py
```

In another shell, exercise the screenshot endpoint directly with a known site URL (uses an existing showcase site to avoid network surprises):

```bash
curl -s -X POST http://127.0.0.1:5555/editor/screenshot \
  -H "Content-Type: application/json" \
  -d '{"url":"https://11ty.rocks/"}'
```

Expected response JSON includes `"success": true`, `"screenshotpath": "/screenshots/11ty-rocks-large.jpg"`, and `"ogpath": "/og-images/11ty-rocks-og.jpg"`.

Then verify both files exist with correct dimensions:

```bash
ls -la /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/og-images/11ty-rocks-og.jpg \
       /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundle.dev/content/og-images/11ty-rocks-og.jpg
sips -g pixelWidth -g pixelHeight \
  /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/og-images/11ty-rocks-og.jpg
```

Expected: both files exist, both 1200×630.

Stop the app (Ctrl+C in the app shell, or `curl -X POST http://127.0.0.1:5555/kill-server` if a kill-server endpoint exists).

- [ ] **Step 4: Visually inspect framing**

Open the generated OG file in Preview to confirm the top of the page (logo/hero) is preserved and only the bottom 45px of the resized image was trimmed:

```bash
open /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/og-images/11ty-rocks-og.jpg
```

Expected: image shows the top portion of the captured page, properly framed for an OG card. If the framing looks wrong, stop and revisit the spec's crop strategy before continuing.

- [ ] **Step 5: Commit**

```bash
cd /Users/Bob/Dropbox/Docs/Sites/social-posting && git add scripts/capture-screenshot.js && git commit -m "Generate OG image alongside screenshot capture" && git push origin main
```

---

## Task 4: Add backfill CLI script

**Files:**
- Create: `scripts/backfill-og-images.js`

Idempotent: skips files where the OG already exists in the bundledb destination. Per-file errors are logged but do not abort the run. Exit code reflects whether any errors occurred.

- [ ] **Step 1: Write the backfill script**

Create `scripts/backfill-og-images.js`:

```js
#!/usr/bin/env node

/**
 * Backfill OG images for existing screenshots.
 *
 * Iterates 11tybundledb/screenshots/*-large.jpg and produces a matching
 * <domain>-og.jpg in both 11tybundledb/og-images/ and
 * 11tybundle.dev/content/og-images/.
 *
 * Idempotent: skips when the OG file already exists in the bundledb
 * destination. To force regeneration, delete the og-images directory
 * (or specific files) and re-run.
 *
 * Usage: node scripts/backfill-og-images.js
 */

"use strict";

const fs = require("fs");
const path = require("path");

const { generateOg } = require("./lib/og-from-screenshot");

const BUNDLEDB_DIR = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb";
const SCREENSHOTS_DIR = path.join(BUNDLEDB_DIR, "screenshots");
const OG_IMAGES_DIR = path.join(BUNDLEDB_DIR, "og-images");
const CONTENT_OG_IMAGES_DIR =
  "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundle.dev/content/og-images";

const LARGE_SUFFIX = "-large.jpg";
const OG_SUFFIX = "-og.jpg";

async function main() {
  if (!fs.existsSync(SCREENSHOTS_DIR)) {
    console.error(`Source directory not found: ${SCREENSHOTS_DIR}`);
    process.exit(1);
  }

  const all = fs.readdirSync(SCREENSHOTS_DIR);
  const sources = all.filter((name) => name.endsWith(LARGE_SUFFIX)).sort();
  const total = sources.length;

  console.log(`Found ${total} screenshots in ${SCREENSHOTS_DIR}`);

  let created = 0;
  let skipped = 0;
  let errors = 0;

  for (let i = 0; i < total; i++) {
    const largeName = sources[i];
    const domain = largeName.slice(0, -LARGE_SUFFIX.length);
    const ogName = `${domain}${OG_SUFFIX}`;
    const sourcePath = path.join(SCREENSHOTS_DIR, largeName);
    const bundledbOgPath = path.join(OG_IMAGES_DIR, ogName);
    const contentOgPath = path.join(CONTENT_OG_IMAGES_DIR, ogName);

    const prefix = `[${i + 1}/${total}] ${domain}`;

    if (fs.existsSync(bundledbOgPath)) {
      console.log(`${prefix} -> skipped`);
      skipped++;
      continue;
    }

    try {
      await generateOg(sourcePath, [bundledbOgPath, contentOgPath]);
      console.log(`${prefix} -> created`);
      created++;
    } catch (err) {
      console.error(`${prefix} -> error: ${err.message}`);
      errors++;
    }
  }

  console.log(`Done. created: ${created}, skipped: ${skipped}, errors: ${errors}`);
  process.exit(errors > 0 ? 1 : 0);
}

main();
```

- [ ] **Step 2: Dry-run on a small sample first**

Before processing all 1590 screenshots, validate against a small sample to catch any pipeline issues early. Create a temp source directory with 5 screenshots and a temp script that points at it.

```bash
mkdir -p /tmp/og-backfill-sample/screenshots /tmp/og-backfill-sample/og-images /tmp/og-backfill-sample/content-og
cp /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/screenshots/11ty-rocks-large.jpg /tmp/og-backfill-sample/screenshots/
cp /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/screenshots/11tybundle-dev-large.jpg /tmp/og-backfill-sample/screenshots/
cp /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/screenshots/11ta-netlify-app-large.jpg /tmp/og-backfill-sample/screenshots/
cp /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/screenshots/100daystooffload-com-large.jpg /tmp/og-backfill-sample/screenshots/
cp /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/screenshots/11ty-deno-dev-large.jpg /tmp/og-backfill-sample/screenshots/
```

Run a one-off invocation of the helper against the sample directory (this avoids modifying the real backfill script for testing):

```bash
cd /Users/Bob/Dropbox/Docs/Sites/social-posting && node -e "
const fs = require('fs');
const path = require('path');
const { generateOg } = require('./scripts/lib/og-from-screenshot');
const SRC = '/tmp/og-backfill-sample/screenshots';
const D1 = '/tmp/og-backfill-sample/og-images';
const D2 = '/tmp/og-backfill-sample/content-og';
(async () => {
  const files = fs.readdirSync(SRC).filter(f => f.endsWith('-large.jpg'));
  for (const f of files) {
    const og = f.replace(/-large\.jpg\$/, '-og.jpg');
    await generateOg(path.join(SRC, f), [path.join(D1, og), path.join(D2, og)]);
    console.log('created', og);
  }
})().catch(e => { console.error(e); process.exit(1); });
"
```

Expected: prints 5 `created <name>-og.jpg` lines. Then verify each output is 1200×630:

```bash
for f in /tmp/og-backfill-sample/og-images/*.jpg; do
  echo "$f"
  sips -g pixelWidth -g pixelHeight "$f"
done
```

Expected: every file shows 1200×630.

- [ ] **Step 3: Visually inspect a few sample outputs**

```bash
open /tmp/og-backfill-sample/og-images/
```

Click through 2-3 OG images. Confirm the top portion of each page is preserved and the framing makes sense for an OG card.

- [ ] **Step 4: Clean up sample**

```bash
rm -rf /tmp/og-backfill-sample
```

- [ ] **Step 5: Run the actual backfill on the full set**

```bash
cd /Users/Bob/Dropbox/Docs/Sites/social-posting && node scripts/backfill-og-images.js
```

Expected: streams `[N/total] <domain> -> created` lines (with `skipped` for the one already created in Task 3). Final line: `Done. created: ~1589, skipped: 1, errors: 0`. Process exits 0.

If `errors > 0`, review stderr lines, address the underlying cause (e.g., a corrupted source screenshot), and re-run — already-created OGs will be skipped.

- [ ] **Step 6: Verify idempotency by re-running**

```bash
cd /Users/Bob/Dropbox/Docs/Sites/social-posting && node scripts/backfill-og-images.js | tail -5
```

Expected: every line reports `skipped`; final summary `created: 0, skipped: ~1590, errors: 0`. Exit code 0.

- [ ] **Step 7: Spot-check a few backfilled OG images**

Pick any 3 sites from across the alphabet:

```bash
sips -g pixelWidth -g pixelHeight \
  /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/og-images/11ty-rocks-og.jpg \
  /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/og-images/11tybundle-dev-og.jpg \
  /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/og-images/100daystooffload-com-og.jpg
ls /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundle.dev/content/og-images/ | wc -l
```

Expected: each spot-checked file is 1200×630; the content/og-images directory contains the same count as bundledb/og-images.

- [ ] **Step 8: Commit the backfill script**

```bash
cd /Users/Bob/Dropbox/Docs/Sites/social-posting && git add scripts/backfill-og-images.js && git commit -m "Add one-shot backfill script for OG images from existing screenshots" && git push origin main
```

(The generated images live in the sibling `11tybundledb` repo; that repo's existing workflows handle committing them.)

---

## Self-Review

**Spec coverage check:**

| Spec section | Plan task |
|---|---|
| Sharp dependency | Task 1 |
| Shared `generateOg(sourcePath, destPaths)` helper | Task 2 |
| `capture-screenshot.js` always-regenerate behavior + `ogpath` JSON field | Task 3 |
| `backfill-og-images.js` one-shot CLI, idempotent skip logic, per-file error handling | Task 4 |
| Storage to both bundledb and content/og-images | Tasks 2, 3, 4 (helper writes both paths) |
| JPEG quality 90 | Task 2 (Sharp pipeline) |
| 1200×630 dimensions via 1200-wide resize + top-anchored extract | Task 2 (Sharp pipeline) |
| Manual verification (capture + backfill spot-checks + idempotency) | Tasks 3, 4 |
| Out-of-scope items (Eleventy meta tags, prebuild_sync changes, db-mgmt UI button) | None — explicitly excluded |

All spec sections covered.

**Placeholder scan:** No TBD/TODO/"implement appropriately" placeholders. Every code step contains complete code; every command is exact.

**Type/name consistency:** `generateOg(sourcePath, destPaths)` — same signature in Tasks 2, 3, 4. Constants `OG_IMAGES_DIR`, `CONTENT_OG_IMAGES_DIR`, `LARGE_SUFFIX`, `OG_SUFFIX`, `ogpath` — used consistently.
