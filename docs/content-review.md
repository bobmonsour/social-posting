# Content Review Feature

## Purpose

When adding a site to the 11ty Bundle database, automatically review the site's content using an AI API to flag potentially hateful, discriminatory, or extremist opinions. This helps the curator catch problematic content before publishing it on 11tybundle.dev.

## Design Principles

- **Warning, not blocker**: The AI review surfaces concerns for the curator to evaluate. It never prevents saving.
- **Minimal friction**: Runs in parallel with existing site fetches, adding only a few seconds.
- **Graceful degradation**: If the review fails (API error, timeout, etc.), the fetch flow continues normally.
- **Low cost**: Uses Claude Haiku for fast, inexpensive classification.

## What Gets Checked

Fetch and analyze text content from up to 3 pages:
1. **Homepage** (always)
2. **/about** page (if it exists)
3. **/author** page (if it exists)
4. **/beliefs** page (if it exists)
5. **1-10 blog post titles** (linked from the homepage, if identifiable)
6. **1-3 blog posts identified as suspect in step 5**

For each page, extract the visible text content (strip nav, footer, boilerplate) and send it to the AI for review.

## AI Prompt Design

The prompt should ask the model to:
- Identify hateful, discriminatory, or extremist content (racism, sexism, homophobia, transphobia, white supremacy, etc.)
- Distinguish between *technical content that happens to discuss sensitive topics* and *content that expresses hateful opinions*
- Return a structured response: `{"flagged": true/false, "confidence": "low"|"medium"|"high", "summary": "brief explanation of concerns"}`
- When not flagged, return `{"flagged": false}` with no summary

The prompt should be stored as a constant in the service module so it's easy to tune over time.

## Architecture

### New Service: `services/content_review.py`

```
content_review.py
  - REVIEW_PROMPT (constant)
  - fetch_page_text(url) -> str
      Fetches a URL, extracts visible text (similar to description.py but returns full body text, not just meta descriptions).
      Strips nav, header, footer, sidebar elements. Returns cleaned text truncated to ~3000 chars.
  - find_subpages(url, soup) -> list[str]
      Given the homepage URL and its parsed HTML, finds the /about page and 1-2 recent blog post URLs.
      Heuristics: look for /about links, then recent post links from the main content area.
  - review_content(url) -> dict
      Main entry point. Fetches homepage, finds subpages, fetches those, sends combined text to Claude API.
      Returns: {"flagged": bool, "confidence": str, "summary": str, "pages_checked": int}
      On any error: returns {"flagged": false, "error": str}
```

**Dependencies**: `anthropic` Python SDK (add to requirements/venv). Uses `ANTHROPIC_API_KEY` env var.

### New Endpoint: `POST /editor/content-review`

In `app.py`, following the same pattern as `/editor/description`:
- Accepts `{"url": "..."}`.
- Calls `review_content(url)`.
- Returns `{"success": true, "flagged": bool, "confidence": str, "summary": str, "pages_checked": int}`.

### Frontend Integration: `editor.js`

**Add to site fetch flow** (the `Promise.all` in the site fetch button handler):
- Add a 5th parallel promise: `fetch('/editor/content-review', ...)`.
- This runs alongside favicon, screenshot, description, and leaderboard fetches.

**Display results as a warning banner** (modeled after the test-data banner):
- If `flagged: true`: show a red/orange warning banner above the form fields.
  - Banner text: "Content Review Warning (confidence: high/medium/low): [summary]"
  - Banner persists until the form is closed or a new fetch is run.
  - Include a "Dismiss" button to hide it (the curator has seen it and made their decision).
- If `flagged: false`: show a brief green status message ("Content review: no concerns found, N pages checked") that fades with the normal status messages.
- If the review failed: show nothing (or a subtle note in the status line like "Content review: unavailable").

**Status message integration**:
- Add content review result to the existing status message aggregation (alongside favicon, screenshot, etc.).

## Configuration

Add to `.env` / `.env.example`:
```
ANTHROPIC_API_KEY=sk-ant-...
```

Add to `config.py`:
```python
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
```

## Cost Estimate

- ~3 pages of text per site, ~3000 chars each = ~9000 chars input (~2500 tokens)
- Claude Haiku response: ~100 tokens
- Cost per site check: well under $0.01
- At typical curation volume (a few sites per week): negligible

## Testing

### `tests/test_content_review.py`

- Mock the Anthropic API with `responses` or `unittest.mock.patch`
- Test `fetch_page_text()` with sample HTML (verify boilerplate stripping)
- Test `find_subpages()` with sample homepage HTML
- Test `review_content()` with mocked API responses (flagged, not flagged, error cases)
- Test the `/editor/content-review` endpoint via the Flask test client

## Future Considerations

- **Caching**: Could cache review results by URL to avoid re-checking the same site. A simple dict or file-based cache with TTL would suffice.
- **Periodic re-checks**: Could add a batch review of all sites in the database (e.g., run monthly). This is a separate feature.
- **Threshold tuning**: The prompt and confidence thresholds can be adjusted based on real-world experience with false positives/negatives.
- **Multiple models**: Could try a secondary model if the primary one is uncertain, but this is likely overkill.

## Implementation Order

1. Add `anthropic` SDK to the venv
2. Create `services/content_review.py` with the three functions
3. Add the `/editor/content-review` endpoint to `app.py`
4. Add `ANTHROPIC_API_KEY` to config
5. Wire into the site fetch `Promise.all` in `editor.js`
6. Add the warning banner UI
7. Write tests
8. Update CLAUDE.md with the new service/endpoint
