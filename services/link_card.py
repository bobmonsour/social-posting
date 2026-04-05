from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from platforms.base import LinkCard


def fetch_og_metadata(url):
    """Fetch Open Graph metadata from a URL. Returns a LinkCard."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; SocialPoster/1.0)"
        }
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        def get_og(prop):
            tag = soup.find("meta", property=f"og:{prop}")
            if tag:
                return tag.get("content", "")
            # Fallback to name attribute
            tag = soup.find("meta", attrs={"name": f"og:{prop}"})
            if tag:
                return tag.get("content", "")
            return ""

        title = get_og("title") or (soup.title.string if soup.title else "")
        description = get_og("description")
        image_url = get_og("image")

        # Fetch thumbnail image data if available
        image_data = b""
        image_mime = ""
        if image_url:
            try:
                # Resolve relative URLs (path-relative, absolute-path, protocol-relative)
                image_url = urljoin(url, image_url)

                img_resp = requests.get(
                    image_url, headers=headers, timeout=10
                )
                img_resp.raise_for_status()
                image_data = img_resp.content
                image_mime = img_resp.headers.get(
                    "content-type", "image/jpeg"
                )
            except Exception:
                pass

        return LinkCard(
            url=url,
            title=title or "",
            description=description or "",
            image_url=image_url or "",
            image_data=image_data,
            image_mime=image_mime,
        )
    except Exception as e:
        return LinkCard(url=url, title="", description=str(e))
