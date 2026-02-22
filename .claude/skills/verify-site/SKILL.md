---
name: verify-site
description: Verify that recently added 11ty Bundle entries appear correctly on the local build at localhost:8080. Automatically starts a local build if one isn't already running.
argument-hint: "[date or 'today' or 'yesterday', default: today]"
disable-model-invocation: true
allowed-tools: Bash(python3 *), Bash(curl *), Bash(cd /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundle.dev && npm run latest)
---

## Verify Site Build

Verify that recently added entries in the 11ty Bundle local build at `http://localhost:8080` rendered correctly. The Chrome browser window can be minimized during verification — all checks use JavaScript DOM queries, not visual inspection.

### Step 1: Identify entries to verify

Read the data files to find entries added on the target date:
- **Date argument**: `$ARGUMENTS` (default to today's date if empty; accept "today", "yesterday", or a `YYYY-MM-DD` date)
- **bundledb.json**: `/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/bundledb.json` — find entries where `Date` starts with the target date. Note the `Title`, `Type`, and `Link` for each.
- **showcase-data.json**: `/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/showcase-data.json` — find site entries where `date` matches the target date. Note image fields: `favicon`, `screenshotpath`.

Group entries by type: blog posts, sites, releases, starters.

If no entries are found for the target date, report that and stop.

### Step 2: Ensure local server is running

Check if `http://localhost:8080` is responding:

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080 --max-time 3
```

If the server is **not running** (curl fails or returns non-200):
1. Tell the user you're starting a local build.
2. Start the Eleventy dev server in the background:
   ```bash
   cd /Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundle.dev && npm run latest
   ```
   Run this via the Bash tool with `run_in_background: true`.
3. Poll `http://localhost:8080` every 3 seconds (up to 60 seconds) until it responds with HTTP 200:
   ```bash
   python3 -c "
import urllib.request, time, sys
for i in range(20):
    try:
        urllib.request.urlopen('http://localhost:8080', timeout=3)
        print(f'Server up after {(i+1)*3} seconds')
        sys.exit(0)
    except Exception:
        time.sleep(3)
print('Timeout waiting for server')
sys.exit(1)
"
   ```
4. If it doesn't come up after 60 seconds, report the failure and stop.

If the server **is already running**, proceed directly to Step 3.

### Step 3: Get browser context

Call `mcp__claude-in-chrome__tabs_context_mcp` (with `createIfEmpty: true`) to get available tabs. Create a new tab with `mcp__claude-in-chrome__tabs_create_mcp` for the verification.

### Step 4: Verify home page

Navigate to `http://localhost:8080` in the new tab.

**For blog posts** — check the "From the firehose" column:
- Use JavaScript execution to find each blog post title in the firehose list
- Record its position (should be near the top, matching recency)
- Check the favicon `<img>` next to each entry: verify `img.complete && img.naturalWidth > 0`

**For sites** — check the "Recent sites" column:
- Use JavaScript execution to find each site title in the recent sites list
- Record its position
- Check the favicon `<img>` next to each entry: verify `img.complete && img.naturalWidth > 0`

Use this JavaScript pattern to check entries and favicons on the home page:

```javascript
// Find entries in a section by heading text
function checkSection(headingText, expectedTitles) {
  const heading = [...document.querySelectorAll('h2')].find(h => h.textContent.includes(headingText));
  const section = heading?.parentElement;
  if (!section) return { error: 'Section not found: ' + headingText };

  const entries = [];
  section.querySelectorAll('a[href]:not([href^="#"])').forEach(a => {
    if (a.textContent.trim() && !a.textContent.includes('RSS') && !a.closest('h2')) {
      entries.push(a.textContent.trim());
    }
  });

  return expectedTitles.map(title => {
    const position = entries.findIndex(e => e.includes(title)) + 1;
    // Find favicon img near this entry
    const link = [...section.querySelectorAll('a')].find(a => a.textContent.includes(title));
    const container = link?.closest('li') || link?.closest('div') || link?.parentElement;
    const img = container?.querySelector('img');
    return {
      title,
      found: position > 0,
      position: position || null,
      faviconLoaded: img ? (img.complete && img.naturalWidth > 0) : false,
      faviconSrc: img?.getAttribute('src') || null
    };
  });
}
```

### Step 5: Verify showcase page (sites only)

If there are site entries to verify:
- Click the "Showcase" link in the navigation header
- Use JavaScript execution to verify each site appears on the showcase page
- For each site, check TWO images:
  1. **Favicon**: `img` with `src` containing the favicon filename — verify `img.complete && img.naturalWidth > 0`
  2. **Site screenshot**: `img` near the same card/entry — verify `img.complete && img.naturalWidth > 0`

The showcase page uses `<figure class="showcase__card">` elements. Each card has:
- A screenshot `<img>` (Eleventy-hashed filename like `/img/xORAx3ZzjF-640.jpeg`)
- A `<figcaption>` containing a favicon `<img>` and a link with the site URL

To find cards for specific sites, locate the `<a>` tag inside `<figcaption>` whose `href` contains a slug derived from the site URL, then walk up to the parent `<figure>`.

Use this JavaScript pattern to check showcase entries:

```javascript
// Check showcase page for site entries
// expectedSites: [{title, faviconFile, linkSlug}, ...]
// linkSlug is a URL fragment to match against figcaption links, e.g. "vanzasetia" or "nutonics"
function checkShowcase(expectedSites) {
  const cards = document.querySelectorAll('figure.showcase__card');
  return expectedSites.map(site => {
    // Find the card by matching the figcaption link href
    const card = [...cards].find(fig => {
      const link = fig.querySelector('figcaption a');
      return link && (link.textContent.includes(site.title) || link.href.includes(site.linkSlug));
    });
    if (!card) return { title: site.title, found: false };

    const imgs = card.querySelectorAll('img');
    const favicon = [...imgs].find(img => (img.getAttribute('src') || '').includes('favicon'));
    const screenshot = [...imgs].find(img => !(img.getAttribute('src') || '').includes('favicon'));

    return {
      title: site.title,
      found: true,
      faviconLoaded: favicon ? (favicon.complete && favicon.naturalWidth > 0) : false,
      faviconSrc: favicon?.getAttribute('src') || null,
      screenshotLoaded: screenshot ? (screenshot.complete && screenshot.naturalWidth > 0) : false,
      screenshotWidth: screenshot ? screenshot.naturalWidth : 0,
      screenshotSrc: screenshot?.getAttribute('src') || null
    };
  });
}
```

### Step 6: Report results

Output a structured verification report:

```
Verification [PASSED|FAILED] (N/N entries)

Home Page — From the firehose:
  [checkmark or X] "Title" — position N, favicon [OK|BROKEN]

Home Page — Recent sites:
  [checkmark or X] "Title" — position N, favicon [OK|BROKEN]

Showcase page:
  [checkmark or X] "Title" — favicon [OK|BROKEN], site image [OK|BROKEN] (Wpx wide)
```

Use checkmark for pass, X for fail. Include specific failure details (e.g., "NOT FOUND in firehose list", "favicon broken — src missing", "site image not loaded").