import os
import re
import subprocess
from datetime import date

import anthropic

import config
from services.content_review import fetch_page_text

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TEMPLATE_PATH = os.path.join(_BASE_DIR, "templates", "11ty-bundle-xx.md")
_BLOG_BASE_PATH = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundle.dev/content/blog"


SUMMARIZE_PROMPT = """Read the following blog post text and write exactly one sentence summarizing what the post is about. The sentence should be concise (under 30 words), informative, and written in third person. Do not use markdown formatting. Respond with only the summary sentence, nothing else."""


def summarize_blog_post(url):
    """Fetch a blog post and return a one-sentence summary via Claude Haiku.

    Returns the summary string, or "[summary unavailable]" on any error.
    """
    if not config.ANTHROPIC_API_KEY:
        return "[summary unavailable]"

    try:
        text = fetch_page_text(url)
        if not text or len(text.strip()) < 50:
            return "[summary unavailable]"

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=128,
            messages=[
                {
                    "role": "user",
                    "content": f"{SUMMARIZE_PROMPT}\n\n--- BLOG POST TEXT ---\n{text}",
                }
            ],
        )

        summary = message.content[0].text.strip()

        # Strip markdown code fences if present
        if summary.startswith("```"):
            lines = summary.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            summary = "\n".join(lines).strip()

        if not summary:
            return "[summary unavailable]"

        return summary

    except Exception:
        return "[summary unavailable]"


def create_blog_post(issue_number, publication_date=None, highlights=None, overwrite=False):
    """Create a new 11ty Bundle blog post from the template.

    Args:
        issue_number: The bundle issue number.
        publication_date: ISO date string (YYYY-MM-DD). Defaults to today.
        highlights: Optional list of dicts with 'author', 'author_site', 'title', 'link' keys.
            Used to populate the Highlights section of the generated markdown.
        overwrite: If True, overwrite an existing file instead of returning an error.

    Returns dict with 'success', 'file_path', and optional 'error'.
    """
    if publication_date is None:
        publication_date = date.today().isoformat()

    # Validate inputs
    try:
        issue_num = int(issue_number)
        if issue_num <= 0:
            return {"success": False, "error": "Issue number must be positive"}
    except (ValueError, TypeError):
        return {"success": False, "error": "Invalid issue number"}

    date_regex = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    if not date_regex.match(publication_date):
        return {"success": False, "error": "Invalid date format"}

    # Build file path
    year = publication_date[:4]
    padded = str(issue_num).zfill(2)
    year_dir = os.path.join(_BLOG_BASE_PATH, year)
    file_name = f"11ty-bundle-{padded}.md"
    file_path = os.path.join(year_dir, file_name)

    # Check if file already exists
    if os.path.exists(file_path) and not overwrite:
        return {"success": False, "error": f"File already exists: {file_name}", "exists": True}

    # Read template
    try:
        with open(_TEMPLATE_PATH, "r") as f:
            content = f.read()
    except OSError as e:
        return {"success": False, "error": f"Cannot read template: {e}"}

    # Replace placeholders
    content = re.sub(r"^bundleIssue:\s*$", f"bundleIssue: {issue_num}", content, flags=re.MULTILINE)
    content = re.sub(r"^date:\s*$", f"date: {publication_date}", content, flags=re.MULTILINE)

    # Replace highlight placeholders with formatted entries
    if highlights:
        highlight_lines = []
        for h in highlights:
            author = h.get("author", "")
            author_site = h.get("author_site", "")
            title = h.get("title", "")
            link = h.get("link", "")
            if author_site:
                line = f"**.** [{author}]({author_site}) - [{title}]({link})"
            else:
                line = f"**.** {author} - [{title}]({link})"
            if h.get("summary"):
                line += f" — {h['summary']}"
            highlight_lines.append(line)
        # Replace the placeholder **.**\n lines between ## Highlights and the next section
        highlights_text = "\n\n".join(highlight_lines)
        content = re.sub(
            r"(## Highlights\n)\n(?:\*\*\.\*\*\n\n)+\*\*\.\*\*\n",
            r"\1\n" + highlights_text + "\n",
            content,
        )

    # Create year directory if needed
    os.makedirs(year_dir, exist_ok=True)

    # Write the file
    with open(file_path, "w") as f:
        f.write(content)

    # Open in VS Code
    try:
        subprocess.Popen(["code", file_path])
    except OSError:
        pass  # VS Code not available, file was still created

    return {"success": True, "file_path": file_path}


def blog_post_exists(issue_number):
    """Check if a blog post file exists for the given issue number."""
    padded = str(int(issue_number)).zfill(2)
    file_name = f"11ty-bundle-{padded}.md"
    # Check current year directory
    year = str(date.today().year)
    file_path = os.path.join(_BLOG_BASE_PATH, year, file_name)
    return os.path.exists(file_path)


def edit_blog_post(issue_number):
    """Open the blog post file in VS Code."""
    padded = str(int(issue_number)).zfill(2)
    file_name = f"11ty-bundle-{padded}.md"
    year = str(date.today().year)
    file_path = os.path.join(_BLOG_BASE_PATH, year, file_name)
    if os.path.exists(file_path):
        try:
            subprocess.Popen(["code", file_path])
            return {"success": True}
        except OSError:
            return {"success": False, "error": "Could not open VS Code"}
    return {"success": False, "error": f"File not found: {file_name}"}


def delete_blog_post(issue_number):
    """Delete the blog post file for the given issue number."""
    padded = str(int(issue_number)).zfill(2)
    file_name = f"11ty-bundle-{padded}.md"
    year = str(date.today().year)
    file_path = os.path.join(_BLOG_BASE_PATH, year, file_name)
    if os.path.exists(file_path):
        os.remove(file_path)
        return {"success": True}
    return {"success": False, "error": f"File not found: {file_name}"}
