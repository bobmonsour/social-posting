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
