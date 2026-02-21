import json
import os

import pytest

import app as app_module


@pytest.fixture
def app(tmp_path):
    """Create a Flask test app with all file paths pointed at temp directories."""
    bundledb_path = tmp_path / "bundledb.json"
    showcase_path = tmp_path / "showcase-data.json"
    history_file = tmp_path / "history.json"
    draft_images_dir = tmp_path / "draft_images"
    backup_dir = tmp_path / "bundledb-backups"
    showcase_backup_dir = tmp_path / "showcase-data-backups"

    # Write empty defaults
    bundledb_path.write_text("[]")
    showcase_path.write_text("[]")
    history_file.write_text("[]")
    draft_images_dir.mkdir()
    backup_dir.mkdir()
    showcase_backup_dir.mkdir()

    flask_app = app_module.app
    flask_app.config["TESTING"] = True
    flask_app.config["BUNDLEDB_PATH"] = str(bundledb_path)
    flask_app.config["SHOWCASE_PATH"] = str(showcase_path)
    flask_app.config["HISTORY_FILE"] = str(history_file)
    flask_app.config["DRAFT_IMAGES_DIR"] = str(draft_images_dir)
    flask_app.config["BUNDLEDB_BACKUP_DIR"] = str(backup_dir)
    flask_app.config["SHOWCASE_BACKUP_DIR"] = str(showcase_backup_dir)

    yield flask_app

    # Clean up config overrides
    for key in ("BUNDLEDB_PATH", "SHOWCASE_PATH", "HISTORY_FILE",
                "DRAFT_IMAGES_DIR", "BUNDLEDB_BACKUP_DIR", "SHOWCASE_BACKUP_DIR", "TESTING"):
        flask_app.config.pop(key, None)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_bundledb():
    return [
        {
            "Issue": 100,
            "Type": "blog post",
            "Title": "Getting Started with Eleventy",
            "Link": "https://example.com/blog/eleventy-start",
            "Date": "2026-01-15",
            "Author": "Jane Doe",
            "Categories": ["Getting Started"],
            "formattedDate": "January 15, 2026",
            "slugifiedAuthor": "jane-doe",
            "slugifiedTitle": "getting-started-with-eleventy",
            "description": "A guide to 11ty",
            "AuthorSite": "https://example.com",
            "AuthorSiteDescription": "Jane's blog",
            "favicon": "/img/favicons/example-com.png",
            "rssLink": "https://example.com/feed.xml",
            "socialLinks": {
                "mastodon": "@jane@mastodon.social",
                "bluesky": "@jane.bsky.social",
            },
        },
        {
            "Issue": 100,
            "Type": "site",
            "Title": "Cool Eleventy Site",
            "Link": "https://cool11ty.dev",
            "Date": "2026-01-10",
            "formattedDate": "January 10, 2026",
            "description": "A cool site built with Eleventy",
            "favicon": "/img/favicons/cool11ty-dev.png",
        },
        {
            "Issue": 99,
            "Type": "release",
            "Title": "Eleventy v3.0.0",
            "Link": "https://github.com/11ty/eleventy/releases/tag/v3.0.0",
            "Date": "2026-01-05",
            "formattedDate": "January 5, 2026",
            "description": "New release of Eleventy",
        },
        {
            "Issue": 99,
            "Type": "starter",
            "Title": "11ty Starter",
            "Link": "https://github.com/user/11ty-starter",
            "Demo": "https://11ty-starter.netlify.app",
            "description": "A starter template",
        },
    ]


@pytest.fixture
def sample_showcase():
    return [
        {
            "title": "Cool Eleventy Site",
            "description": "A cool site built with Eleventy",
            "link": "https://cool11ty.dev",
            "date": "2026-01-10",
            "formattedDate": "January 10, 2026",
            "favicon": "/img/favicons/cool11ty-dev.png",
            "screenshotpath": "/screenshots/cool11ty-dev.jpg",
            "leaderboardLink": "https://www.11ty.dev/speedlify/cool11ty-dev/",
        }
    ]


@pytest.fixture
def bwe_content():
    return (
        "- TO BE POSTED -\n"
        "[My Cool Site](https://mycoolsite.dev)\n"
        "[Another Site](https://another.dev)\n"
        "\n"
        "- ALREADY POSTED -\n"
        "2026-01-10 [Posted Site](https://posted.dev) \u2014 Posted to Mastodon\n"
    )


@pytest.fixture
def bwe_file(tmp_path, bwe_content):
    path = tmp_path / "built-with-eleventy.md"
    path.write_text(bwe_content)
    return path
