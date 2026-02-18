import json
import re

import requests
from bs4 import BeautifulSoup


def extract_description(url):
    """Extract site description using multi-source meta tag strategy.

    Mirrors the extraction logic from dbtools/lib/getdescription.js.
    """
    if "youtube.com" in url:
        return "YouTube video"

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; SocialPoster/1.0)"
        }
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return ""

    def get_meta_content(attr_name, attr_value):
        """Case-insensitive meta tag lookup."""
        for tag in soup.find_all("meta"):
            val = tag.get(attr_name, "")
            if val and val.lower() == attr_value.lower():
                content = tag.get("content")
                if content:
                    return content
        return None

    # Try multiple sources in order of preference
    description = (
        # 1. Standard meta description
        get_meta_content("name", "description")
        # 2. Open Graph description
        or (soup.find("meta", property="og:description") or {}).get("content")
        # 3. Twitter Card description
        or get_meta_content("name", "twitter:description")
        # 4. Dublin Core description
        or get_meta_content("name", "DC.description")
        # 5. Schema.org microdata
        or (soup.find("meta", itemprop="description") or {}).get("content")
    )

    # 6. Try JSON-LD schema.org
    if not description:
        for script in soup.find_all("script", type="application/ld+json"):
            if description:
                break
            try:
                json_ld = json.loads(script.string or "")
                items = json_ld if isinstance(json_ld, list) else [json_ld]
                for item in items:
                    if isinstance(item, dict):
                        if item.get("description"):
                            description = item["description"]
                            break
                        graph = item.get("@graph", [])
                        if isinstance(graph, list):
                            for g in graph:
                                if isinstance(g, dict) and g.get("description"):
                                    description = g["description"]
                                    break
            except (json.JSONDecodeError, TypeError):
                pass

    if not description:
        return ""

    # Sanitize (mirrors getdescription.js)
    text = description
    text = re.sub(r"[<>]", "", text)
    text = re.sub(r'&(?!(?:[a-z\d]+|#\d+|#x[a-f\d]+);)', "&amp;", text, flags=re.IGNORECASE)
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&#39;")
    text = re.sub(r"\s+", " ", text)
    # Remove control characters
    text = re.sub(r"[\u0000-\u001f\u007f-\u009f]", "", text)
    # Remove zero-width characters
    text = re.sub(r"[\u200b-\u200d\ufeff]", "", text)
    # Remove directional text markers
    text = re.sub(r"[\u202a-\u202e]", "", text)
    # Remove soft hyphens
    text = text.replace("\u00ad", "")
    # Convert non-breaking and unicode spaces
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[\u2000-\u200a]", " ", text)
    # Remove line/paragraph separators
    text = re.sub(r"[\u2028\u2029]", " ", text)
    # Remove word joiners
    text = text.replace("\u2060", "")
    # Remove interlinear annotation characters
    text = re.sub(r"[\ufff9-\ufffb]", "", text)
    text = text.strip()[:300]

    # Convert markdown links to HTML
    if "[" in text:
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)

    return text
