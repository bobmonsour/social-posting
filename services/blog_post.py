import os
import re
import subprocess
from datetime import date

_DBTOOLS_DIR = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/dbtools"
_TEMPLATE_PATH = os.path.join(_DBTOOLS_DIR, "11ty-bundle-xx.md")
_BLOG_BASE_PATH = os.path.join(_DBTOOLS_DIR, "..", "11tybundle.dev", "content", "blog")


def create_blog_post(issue_number, publication_date=None):
    """Create a new 11ty Bundle blog post from the template.

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
    if os.path.exists(file_path):
        return {"success": False, "error": f"File already exists: {file_name}"}

    # Read template
    try:
        with open(_TEMPLATE_PATH, "r") as f:
            content = f.read()
    except OSError as e:
        return {"success": False, "error": f"Cannot read template: {e}"}

    # Replace placeholders
    content = re.sub(r"^bundleIssue:\s*$", f"bundleIssue: {issue_num}", content, flags=re.MULTILINE)
    content = re.sub(r"^date:\s*$", f"date: {publication_date}", content, flags=re.MULTILINE)

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
