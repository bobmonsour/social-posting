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
