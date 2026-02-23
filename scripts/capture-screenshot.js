#!/usr/bin/env node

/**
 * Capture a screenshot of a URL using Puppeteer.
 * Usage: node capture-screenshot.js <url>
 *
 * Saves to both 11tybundledb/screenshots/ and content/screenshots/.
 * Outputs JSON to stdout: {success, filename, screenshotpath}
 *
 */

const puppeteer = require("puppeteer");
const path = require("path");
const fs = require("fs");

const BUNDLEDB_DIR = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb";
const SCREENSHOTS_DIR = path.join(BUNDLEDB_DIR, "screenshots");
const CONTENT_SCREENSHOTS_DIR =
  "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundle.dev/content/screenshots";

async function main() {
  const url = process.argv[2];
  if (!url) {
    console.log(JSON.stringify({ success: false, error: "No URL provided" }));
    process.exit(1);
  }

  // Generate filename from hostname
  const parsed = new URL(url);
  const domain = parsed.hostname.replace(/[./]/g, "-");
  const filename = `${domain}-large.jpg`;
  const screenshotpath = `/screenshots/${filename}`;

  // Ensure directories exist
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
  fs.mkdirSync(CONTENT_SCREENSHOTS_DIR, { recursive: true });

  let browser;
  try {
    browser = await puppeteer.launch({
      headless: "new",
      args: ["--no-sandbox", "--disable-setuid-sandbox"],
    });

    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });
    await page.goto(url, { waitUntil: "networkidle0", timeout: 30000 });

    // Wait extra time for animations/lazy loads
    await new Promise((resolve) => setTimeout(resolve, 3000));

    const dbtoolsPath = path.join(SCREENSHOTS_DIR, filename);
    await page.screenshot({
      path: dbtoolsPath,
      type: "jpeg",
      quality: 100,
    });

    // Copy to content directory
    const contentPath = path.join(CONTENT_SCREENSHOTS_DIR, filename);
    fs.copyFileSync(dbtoolsPath, contentPath);

    console.log(
      JSON.stringify({ success: true, filename, screenshotpath })
    );
  } catch (err) {
    console.log(
      JSON.stringify({ success: false, error: err.message })
    );
    process.exit(1);
  } finally {
    if (browser) await browser.close();
  }
}

main();
