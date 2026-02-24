# Showcase Content Review — Bulk Scan Plan

## Goal

Iterate over all ~1,480 entries in `showcase-data.json` and run content review against each site. Produce an HTML report listing only flagged sites, with links to the specific pages where concerning content was found.

## Architecture

### New file: `services/showcase_review.py`

A standalone script (runnable via `python -m services.showcase_review`) that:

1. **Loads `showcase-data.json`** and extracts all unique `link` values.
2. **Iterates through each site**, calling a bulk-oriented review function.
3. **Rate-limits requests** to stay safely below Anthropic API limits.
4. **Saves progress incrementally** so the scan can be resumed if interrupted.
5. **Adds clean sites to a permanent allowlist** so they are skipped on future runs.
6. **Generates an HTML report** at the end with only flagged sites.

### Changes to `services/content_review.py`

The existing `review_content()` and supporting functions will be updated to support deeper page coverage. These changes apply to both the single-site editor flow and the bulk scan.

#### Expanded subpage discovery

`find_subpages()` currently checks: `/about`, `/author`, `/beliefs`

**Add**: `/values`, `/now`

These are common on personal sites — `/now` is a [widespread convention](https://nownownow.com/about) where site owners describe what they're currently focused on and often share personal worldview statements. `/values` serves a similar purpose. Both are low-cost to probe (same-origin link scan, no extra HTTP if the link isn't present on the homepage).

#### Blog post content fetching

Currently, `find_subpages()` returns up to 10 blog post `(title, url)` tuples, but only the **titles** are sent to Haiku — the actual post content is never fetched.

**Change**: Fetch full text for **up to 3 blog posts** (not just titles). Selection strategy:
- Take the 3 most recent posts from the homepage links (these are most likely to reflect current views).
- Each post is fetched via `fetch_page_text()` (same stripping/3,000-char truncation as other pages).
- Remaining blog post titles (up to 7 more) are still sent as title-only, as today.

**Token budget impact**: Homepage (3K) + up to 5 subpages (15K worst case, but typically 1–2 match = 3–6K) + 3 blog posts (9K) could exceed the current 12,000-char combined limit. **Increase the combined truncation to 18,000 chars** (~4,500–6,000 input tokens). This stays well within Haiku's context window and only modestly increases per-request token cost.

#### Prompt updates

Three additions to the "IMPORTANT distinctions" section of `REVIEW_PROMPT`:

1. **Anti-AI opinions**: "Negative opinions about AI, AI-generated content, or AI tools are NOT concerning, even if expressed strongly or harshly."
2. **Dead/parked sites**: "Dead sites, parked domains, placeholder pages, and domain-for-sale pages are NOT concerning."
3. **Update the existing satire carve-out** to also cover strong language: "Strong language, profanity, or venting frustration is NOT concerning unless it targets protected groups."

The full updated prompt:

```
You are reviewing the text content of a personal website to identify hateful,
discriminatory, or extremist opinions. This is for a curated directory of web
development sites.

Analyze the following text extracted from a website. Look for:
- Racism, white supremacy, or ethnonationalism
- Sexism, misogyny, or incel ideology
- Homophobia, transphobia, or anti-LGBTQ rhetoric
- Religious extremism or hate toward religious groups
- Antisemitism or Islamophobia
- Ableism or dehumanizing language about disabled people
- Advocacy of political violence or authoritarianism
- Conspiracy theories rooted in hate (e.g., "great replacement", QAnon)

IMPORTANT distinctions:
- Technical blog posts discussing web development, programming, or technology
  are NOT concerning, even if they use terms like "master/slave" in technical
  contexts.
- Personal opinions on non-hateful political topics (taxes, regulation, etc.)
  are NOT concerning.
- Religious content is NOT concerning unless it advocates hatred or
  discrimination.
- Satire, humor, strong language, or profanity is NOT concerning unless it
  targets protected groups or promotes genuine hatred.
- Negative opinions about AI, AI-generated content, or AI tools are NOT
  concerning, even if expressed strongly or harshly.
- Dead sites, parked domains, placeholder pages, and domain-for-sale pages
  are NOT concerning.

Respond with ONLY a JSON object (no markdown, no code fences):
- If concerning content is found: {"flagged": true, "confidence": "low" or
  "medium" or "high", "summary": "brief explanation of the specific concerns"}
- If no concerning content is found: {"flagged": false}
```

### Rate Limiting Strategy

Based on [Anthropic's rate limit documentation](https://docs.claude.com/en/api/rate-limits):

- **Tier 1**: 50 requests/min, 50K input tokens/min
- **Tier 3**: 2,000 requests/min, 1M input tokens/min

Each review call makes **1 Anthropic API call** (plus several plain HTTP fetches to the site itself). With the increased combined text limit (18,000 chars), expect ~4,500–6,000 input tokens per call.

**Conservative approach for Tier 1 (50 RPM, 50K ITPM)**:
- **1 request every 2 seconds** (30 RPM) — well under the 50 RPM limit
- At ~6K input tokens per request and 30 RPM, that's ~180K tokens/min at full speed, which exceeds Tier 1's 50K ITPM. To stay safe: **1 request every 4 seconds** (15 RPM, ~90K ITPM) — or keep 2s if on Tier 2+ (which has 100K+ ITPM).
- **Estimated total time at 4s delay**: 1,480 sites × 4s = ~99 minutes for API calls, plus HTTP fetch time per site (homepage + subpages + blog posts) — **expect ~2–2.5 hours total** for the initial full scan.
- At 2s delay (Tier 2+): **expect ~60–90 minutes**.

The delay should be configurable via a command-line argument so it can be lowered for higher-tier accounts.

### Cleared Sites Allowlist

Sites that pass content review (not flagged, no error) are permanently recorded in a **cleared sites allowlist** (`data/showcase-cleared-sites.json`). This file persists across scan runs and serves as the primary mechanism for avoiding redundant API calls.

- **Format**: A JSON object keyed by normalized URL, with the review date:
  ```json
  {
    "https://example.com/": {"cleared": "2026-02-24", "title": "Example Site"},
    "https://another.dev/": {"cleared": "2026-02-24", "title": "Another Dev"}
  }
  ```
- **Skip logic**: At the start of each run, the allowlist is loaded. Any site whose URL appears in the allowlist is skipped entirely — no HTTP fetches, no API call.
- **Population**: After each successful, non-flagged review (i.e., `flagged: false` with no `error` key), the site is appended to the allowlist and the file is saved immediately.
- **Flagged sites are never added** to the allowlist, so they will be re-reviewed on every subsequent run (allowing the site owner time to address concerns).
- **Error sites are never added** either — network errors are transient, so those sites should be retried next run.
- **Manual removal**: To force re-review of a specific site, delete its entry from the JSON file. To re-review all sites, delete the file or use `--ignore-allowlist`.
- **Location**: `data/showcase-cleared-sites.json` — in the existing `data/` directory alongside `insights-exclusions.json`, since this is project-scoped configuration data (not output).

**Impact on subsequent runs**: After the initial full scan, subsequent runs only need to review:
- Newly added sites (not yet in the allowlist)
- Previously flagged sites (to check if concerns have been addressed)
- Previously errored sites (transient network failures)

This means follow-up runs should complete in seconds to minutes rather than hours.

### Progress / Resume Support (Within a Single Run)

- Results for the *current run* are written incrementally to a JSON file (`showcase-review-results.json`) in the project root.
- Format: `{"reviewed": {"https://example.com": {<review_content result>}, ...}, "started": "ISO timestamp", "last_updated": "ISO timestamp"}`
- On startup, if the results file exists, already-reviewed URLs are skipped (in addition to allowlisted URLs).
- This means the scan can be interrupted (Ctrl+C) and resumed by re-running the script.
- The progress file is complementary to the allowlist: the allowlist is permanent (across runs), while the progress file handles mid-run interruptions. After a run completes successfully, the progress file can be deleted (all clean sites will already be in the allowlist).

### Error Handling

- Sites that fail to fetch (timeout, DNS error, etc.) are recorded with `{"flagged": false, "error": "..."}` and skipped — same as the existing `review_content()` behavior.
- If an Anthropic rate limit error (429) is hit despite the delay, the script backs off exponentially (wait 30s, 60s, 120s) and retries up to 3 times before recording an error and moving on.

## Implementation Steps

### 1. Update `services/content_review.py`

- Add `/values` and `/now` to the `known_paths` list in `find_subpages()`.
- Change `find_subpages()` return to include a `blog_posts_to_fetch` list (first 3) separate from `blog_titles_only` (remaining up to 7).
- In `review_content()`, fetch full text for the 3 blog posts via `fetch_page_text()` and include as `=== BLOG POST (url) ===` sections.
- Increase combined text truncation from 12,000 to 18,000 chars.
- Update `REVIEW_PROMPT` with the three new carve-outs (anti-AI, dead sites, strong language).

### 2. Create `services/showcase_review.py`

```python
# Pseudocode outline

ALLOWLIST_PATH = "data/showcase-cleared-sites.json"

def load_sites():
    """Load showcase-data.json, return list of {title, link} dicts."""

def load_allowlist(path=ALLOWLIST_PATH):
    """Load cleared-sites JSON if present, return dict of cleared URLs."""

def save_allowlist(allowlist, path=ALLOWLIST_PATH):
    """Write cleared-sites dict to JSON file."""

def load_progress(results_path):
    """Load existing results file if present, return dict of reviewed URLs."""

def save_progress(results_path, results_data):
    """Write results dict to JSON file."""

def run_review(delay=2.0, results_path="showcase-review-results.json", ignore_allowlist=False, limit=None):
    """Main loop: iterate sites, call review_content(), rate-limit, save progress.

    Args:
        limit: Max sites to review this run. None = unlimited (full run), 10 = test mode.
    """
    sites = load_sites()
    allowlist = {} if ignore_allowlist else load_allowlist()
    progress = load_progress(results_path)
    reviewed_count = 0

    for i, site in enumerate(sites):
        url = site["link"]
        if url in allowlist:
            continue  # permanently cleared on a prior run
        if url in progress["reviewed"]:
            continue  # already reviewed this run
        if limit is not None and reviewed_count >= limit:
            break  # test mode cap reached

        print(f"[{reviewed_count+1}/{limit or '?'}] Reviewing {url}...")
        result = review_content(url)  # existing function (now with deeper coverage)
        progress["reviewed"][url] = {
            "title": site["title"],
            **result
        }
        save_progress(results_path, progress)
        reviewed_count += 1

        # Add to permanent allowlist if clean (not flagged, no error)
        if not result.get("flagged") and "error" not in result:
            allowlist[url] = {"cleared": date.today().isoformat(), "title": site["title"]}
            save_allowlist(allowlist)

        if result.get("error") and "rate" in result["error"].lower():
            # Back off on rate limit errors
            handle_rate_limit_backoff()
        else:
            time.sleep(delay)

def generate_report(results_path, output_path="showcase-review-report.html"):
    """Read results JSON, produce HTML report with only flagged sites."""
```

### 3. HTML Report Format

A self-contained HTML file with inline CSS (no external dependencies):

- **Header**: "Showcase Content Review Report" with date/time of generation, total sites reviewed, total flagged count.
- **Summary stats**: Sites reviewed, sites flagged, sites with errors (couldn't fetch), review duration.
- **Flagged sites list** (sorted by confidence: high → medium → low):
  - Site title (linked to the site URL)
  - Confidence level (with color coding: high=red, medium=orange, low=yellow)
  - Summary of concerns (from the AI response)
  - List of pages checked (as clickable links) — these come from the `pages` array in the review result
  - Number of blog titles checked (if any)

### 4. CLI Interface

On launch, the script presents an interactive prompt:

```
Showcase Content Review
=======================
1,482 sites in showcase-data.json
1,200 already cleared (allowlist)
282 sites to review

Run mode:
  [T] Test run — review first 10 sites only
  [F] Full run — review all 282 remaining sites

Choose [T/F]:
```

- **Test mode** processes only the first 10 non-allowlisted sites. Useful for verifying the setup, checking prompt behavior, and estimating timing before committing to a full run. Results are still saved to the progress file and clean sites are still added to the allowlist — so test runs aren't wasted work.
- **Full mode** processes all remaining sites.
- **Single-site mode** (`--site=<url>`) reviews one specific URL. Bypasses the allowlist for that URL (always reviews it, even if previously cleared). Prints the result to the terminal and does NOT add the site to the allowlist or progress file — this is a quick ad-hoc check, not part of the batch workflow. The URL does not need to be in `showcase-data.json`.
- The `--test`, `--full`, and `--site` CLI flags skip the interactive prompt. All three are mutually exclusive.

```bash
# Interactive mode (prompts for test vs full)
source .venv/bin/activate && python -m services.showcase_review

# Skip prompt — run in test mode (first 10 sites)
python -m services.showcase_review --test

# Skip prompt — run full scan
python -m services.showcase_review --full

# Run with faster rate (for higher-tier API accounts)
python -m services.showcase_review --full --delay 0.5

# Review a single site (ad-hoc check, not saved to allowlist/progress)
python -m services.showcase_review --site=https://example.com

# Example output for --site:
#   Reviewing https://example.com...
#   Pages checked: 3 (homepage, /about, /now)
#   Blog titles checked: 5
#   Result: NOT FLAGGED
#
# Or if flagged:
#   Result: FLAGGED (confidence: high)
#   Summary: Site contains white nationalist rhetoric on the /beliefs page.

# Generate/regenerate the HTML report from existing results
python -m services.showcase_review --report-only

# Re-review ALL sites, ignoring the cleared-sites allowlist
python -m services.showcase_review --full --ignore-allowlist

# Specify custom output paths
python -m services.showcase_review --results showcase-review-results.json --output showcase-review-report.html
```

Uses `argparse` for CLI args. `--test`, `--full`, and `--site` are mutually exclusive; if none is provided, the interactive prompt is shown.

### 5. Integration with the App (Optional, Future)

Not in scope for initial implementation, but the report could later be:
- Linked from the DB Management page
- Triggered via a button in the editor

### 6. Tests

**Update `tests/test_content_review.py`**:
- Test that `find_subpages()` detects `/values` and `/now` links
- Test that blog post full text is fetched for the first 3 posts
- Test that remaining blog titles are still included as title-only
- Test updated prompt carve-outs (mock Haiku responses for anti-AI content, dead sites, strong language)

**Add `tests/test_showcase_review.py`**:
- Test `load_sites()` with sample showcase data
- Test allowlist save/load round-trip
- Test that allowlisted sites are skipped (no API call made)
- Test that flagged sites are NOT added to the allowlist
- Test that errored sites are NOT added to the allowlist
- Test that clean sites ARE added to the allowlist after review
- Test `--ignore-allowlist` bypasses the allowlist
- Test `--test` limits processing to first 10 non-allowlisted sites
- Test `--site` reviews a single URL, prints result, and does not modify allowlist or progress
- Test progress save/load round-trip
- Test `generate_report()` produces valid HTML with correct flagged entries
- Test resume logic (skips already-reviewed sites within a run)
- Mock `review_content()` to avoid real API calls
- Test rate-limit backoff logic

## File Changes

| File | Change |
|------|--------|
| `services/content_review.py` | **Modified** — expanded subpages, blog post fetching, updated prompt |
| `services/showcase_review.py` | **New** — bulk review script + report generator |
| `data/showcase-cleared-sites.json` | **New** (generated at runtime) — permanent allowlist of cleared sites |
| `tests/test_content_review.py` | **Modified** — tests for expanded coverage |
| `tests/test_showcase_review.py` | **New** — tests for bulk review |

## Open Questions

1. **Delay tuning**: The 2-second default is conservative for Tier 1 but may need to be 4 seconds given the increased token usage. What tier is the Anthropic API key on? A higher tier could cut the runtime significantly.
2. **Report location**: Should the HTML report go in the project root, or somewhere else (e.g., `docs/` or a `reports/` directory)?
