import json
import re
from urllib.parse import urljoin, urlparse

import anthropic
import requests
from bs4 import BeautifulSoup

import config

REVIEW_PROMPT = """You are reviewing the text content of a personal website to identify hateful, discriminatory, or extremist opinions. This is for a curated directory of web development sites.

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
- Technical blog posts discussing web development, programming, or technology are NOT concerning, even if they use terms like "master/slave" in technical contexts.
- Personal opinions on non-hateful political topics (taxes, regulation, etc.) are NOT concerning.
- Religious content is NOT concerning unless it advocates hatred or discrimination.
- Satire or humor is NOT concerning unless it promotes genuine hatred.

Respond with ONLY a JSON object (no markdown, no code fences):
- If concerning content is found: {"flagged": true, "confidence": "low" or "medium" or "high", "summary": "brief explanation of the specific concerns"}
- If no concerning content is found: {"flagged": false}"""


def fetch_page_text(url):
    """Fetch a URL and extract visible body text, stripping boilerplate elements."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; SocialPoster/1.0)"}
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        resp.raise_for_status()
    except Exception:
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove boilerplate elements
    for tag in soup.find_all(["nav", "header", "footer", "aside", "script", "style"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Truncate to ~3000 chars
    return text[:3000]


def find_subpages(url, soup):
    """Find /about, /author, /beliefs pages and blog post links from homepage HTML.

    Returns (subpage_urls, blog_titles) where blog_titles is a list of
    (title, url) tuples for blog post links found on the page.
    """
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    subpage_urls = []
    blog_links = []

    # Look for known subpages
    known_paths = ["/about", "/about/", "/author", "/author/", "/beliefs", "/beliefs/"]
    for link in soup.find_all("a", href=True):
        href = link["href"]
        full_url = urljoin(url, href)
        full_parsed = urlparse(full_url)

        # Only consider same-origin links
        if full_parsed.netloc != parsed.netloc:
            continue

        path = full_parsed.path.rstrip("/").lower()
        if path in [p.rstrip("/") for p in known_paths] and full_url not in subpage_urls:
            subpage_urls.append(full_url)

    # Look for blog post links (articles, post titles)
    # Heuristic: links inside <article>, <main>, or with common blog URL patterns
    content_area = soup.find("main") or soup.find("article") or soup
    for link in content_area.find_all("a", href=True):
        href = link["href"]
        full_url = urljoin(url, href)
        full_parsed = urlparse(full_url)

        if full_parsed.netloc != parsed.netloc:
            continue

        # Skip navigation-like links
        path = full_parsed.path
        if path in ("/", "") or path.rstrip("/").lower() in [p.rstrip("/") for p in known_paths]:
            continue

        title = link.get_text(strip=True)
        if title and len(title) > 10 and len(path) > 5:
            blog_links.append((title, full_url))

    # Deduplicate blog links by URL
    seen = set()
    unique_blog_links = []
    for title, link_url in blog_links:
        if link_url not in seen:
            seen.add(link_url)
            unique_blog_links.append((title, link_url))

    return subpage_urls[:3], unique_blog_links[:10]


def review_content(url):
    """Review a site's content for hateful/discriminatory/extremist material.

    Fetches homepage + subpages, sends combined text to Claude Haiku.
    Returns dict with flagged, confidence, summary, pages_checked keys.
    On any error, returns {"flagged": False, "error": "..."}.
    """
    if not config.ANTHROPIC_API_KEY:
        return {"flagged": False, "error": "ANTHROPIC_API_KEY not configured"}

    try:
        # Fetch homepage
        headers = {"User-Agent": "Mozilla/5.0 (compatible; SocialPoster/1.0)"}
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        resp.raise_for_status()
        homepage_soup = BeautifulSoup(resp.text, "html.parser")

        # Extract homepage text (work on a copy since find_subpages needs the original)
        soup_copy = BeautifulSoup(resp.text, "html.parser")
        for tag in soup_copy.find_all(["nav", "header", "footer", "aside", "script", "style"]):
            tag.decompose()
        homepage_text = re.sub(r"\s+", " ", soup_copy.get_text(separator=" ")).strip()[:3000]

        pages_fetched = [url]
        all_text = [f"=== HOMEPAGE ({url}) ===\n{homepage_text}"]

        # Find subpages and blog post titles
        subpage_urls, blog_links = find_subpages(url, homepage_soup)

        # Fetch subpages
        for sub_url in subpage_urls:
            text = fetch_page_text(sub_url)
            if text:
                pages_fetched.append(sub_url)
                all_text.append(f"=== SUBPAGE ({sub_url}) ===\n{text}")

        # Include blog post titles for the model to assess
        if blog_links:
            titles_text = "\n".join(f"- {title}" for title, _ in blog_links)
            all_text.append(f"=== BLOG POST TITLES ===\n{titles_text}")

        # Send to Claude Haiku
        combined = "\n\n".join(all_text)
        # Truncate combined text to ~12000 chars to stay within reasonable token limits
        combined = combined[:12000]

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[
                {
                    "role": "user",
                    "content": f"{REVIEW_PROMPT}\n\n--- WEBSITE CONTENT ---\n{combined}",
                }
            ],
        )

        response_text = message.content[0].text.strip()

        # Strip markdown code fences if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Remove first line (```json) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            response_text = "\n".join(lines).strip()

        result = json.loads(response_text)
        result["pages_checked"] = len(pages_fetched)
        result["pages"] = pages_fetched
        if blog_links:
            result["blog_titles_checked"] = len(blog_links)
        return result

    except json.JSONDecodeError:
        return {"flagged": False, "error": "Could not parse AI response"}
    except Exception as e:
        return {"flagged": False, "error": str(e)}
