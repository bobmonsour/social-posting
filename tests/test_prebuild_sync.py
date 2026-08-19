"""Tests for services/prebuild_sync.py - pre-build git sync and asset copy."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from services import prebuild_sync


class TestSyncBundledbRepo:
    """Tests for sync_bundledb_repo()."""

    @patch("services.prebuild_sync.subprocess.run")
    def test_no_changes_to_commit(self, mock_run):
        """When there are no local changes, should still pull and push."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),  # git add
            MagicMock(returncode=0, stdout="", stderr=""),  # git status
            MagicMock(returncode=0, stdout="Already up to date.", stderr=""),  # git pull
            MagicMock(returncode=0, stdout="", stderr=""),  # git push
        ]

        result = prebuild_sync.sync_bundledb_repo()

        assert result["success"] is True
        assert "No local changes to commit" in result["message"]
        assert "Already up to date" in result["message"]
        assert mock_run.call_count == 4

    @patch("services.prebuild_sync.subprocess.run")
    def test_with_local_changes(self, mock_run):
        """When there are local changes, should commit, pull, and push."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),  # git add
            MagicMock(returncode=0, stdout="M bundledb.json", stderr=""),  # git status
            MagicMock(returncode=0, stdout="", stderr=""),  # git commit
            MagicMock(returncode=0, stdout="Current branch main is up to date.", stderr=""),  # git pull
            MagicMock(returncode=0, stdout="", stderr=""),  # git push
        ]

        result = prebuild_sync.sync_bundledb_repo()

        assert result["success"] is True
        assert "Committed local changes" in result["message"]
        assert mock_run.call_count == 5

    @patch("services.prebuild_sync.subprocess.run")
    def test_git_add_fails(self, mock_run):
        """When git add fails, should return error."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="fatal: error")

        result = prebuild_sync.sync_bundledb_repo()

        assert result["success"] is False
        assert "git add failed" in result["message"]

    @patch("services.prebuild_sync.subprocess.run")
    def test_git_commit_fails(self, mock_run):
        """When git commit fails, should return error."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),  # git add
            MagicMock(returncode=0, stdout="M bundledb.json", stderr=""),  # git status
            MagicMock(returncode=1, stdout="", stderr="error: commit failed"),  # git commit
        ]

        result = prebuild_sync.sync_bundledb_repo()

        assert result["success"] is False
        assert "git commit failed" in result["message"]

    @patch("services.prebuild_sync.subprocess.run")
    def test_rebase_conflict(self, mock_run):
        """When pull --rebase has a conflict, should abort and return error."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),  # git add
            MagicMock(returncode=0, stdout="", stderr=""),  # git status (no changes)
            MagicMock(returncode=1, stdout="", stderr="CONFLICT in bundledb.json"),  # git pull --rebase
            MagicMock(returncode=0, stdout="", stderr=""),  # git rebase --abort
        ]

        result = prebuild_sync.sync_bundledb_repo()

        assert result["success"] is False
        assert "Rebase conflict detected" in result["message"]

    @patch("services.prebuild_sync.subprocess.run")
    def test_push_fails(self, mock_run):
        """When git push fails, should return error."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),  # git add
            MagicMock(returncode=0, stdout="", stderr=""),  # git status
            MagicMock(returncode=0, stdout="Already up to date.", stderr=""),  # git pull
            MagicMock(returncode=1, stdout="", stderr="error: push failed"),  # git push
        ]

        result = prebuild_sync.sync_bundledb_repo()

        assert result["success"] is False
        assert "git push failed" in result["message"]


class TestLoadRecentIssueEntries:
    """Tests for load_recent_issue_entries()."""

    def test_loads_entries_from_latest_and_prior_issues(self, tmp_path):
        """Should load entries from both the latest issue and the prior issue."""
        bundledb = [
            {"Issue": 100, "Type": "blog post", "Title": "Latest Post", "Link": "https://a.com", "favicon": "/img/favicons/a.png"},
            {"Issue": 100, "Type": "site", "Title": "Latest Site", "Link": "https://b.com", "favicon": "/img/favicons/b.png"},
            {"Issue": 99, "Type": "blog post", "Title": "Prior Post", "Link": "https://c.com", "favicon": "/img/favicons/c.png"},
            {"Issue": 99, "Type": "starter", "Title": "Prior Starter", "Link": "https://d.com", "favicon": "/img/favicons/d.png", "screenshotpath": "/screenshots/d.jpg"},
            {"Issue": 98, "Type": "blog post", "Title": "Old Post", "Link": "https://old.com"},
        ]
        showcase = [
            {"title": "Latest Site", "link": "https://b.com", "screenshotpath": "/screenshots/b.jpg"},
        ]

        bundledb_path = tmp_path / "bundledb.json"
        showcase_path = tmp_path / "showcase-data.json"
        bundledb_path.write_text(json.dumps(bundledb))
        showcase_path.write_text(json.dumps(showcase))

        entries, issue_numbers = prebuild_sync.load_recent_issue_entries(
            str(bundledb_path), str(showcase_path)
        )

        assert issue_numbers == [100, 99]
        assert len(entries) == 4
        titles = {e["Title"] for e in entries}
        assert titles == {"Latest Post", "Latest Site", "Prior Post", "Prior Starter"}
        # Old Post from issue 98 should NOT be included
        assert "Old Post" not in titles

    def test_loads_all_entry_types_including_starters(self, tmp_path):
        """Should load all entry types including starters."""
        bundledb = [
            {"Issue": 100, "Type": "blog post", "Title": "Blog Post", "Link": "https://a.com", "favicon": "/img/favicons/a.png"},
            {"Issue": 100, "Type": "site", "Title": "Site", "Link": "https://b.com", "favicon": "/img/favicons/b.png"},
            {"Issue": 100, "Type": "starter", "Title": "Starter", "Link": "https://c.com", "favicon": "/img/favicons/c.png", "screenshotpath": "/screenshots/c.jpg"},
            {"Issue": 100, "Type": "release", "Title": "Release", "Link": "https://d.com", "favicon": "/img/favicons/d.png"},
        ]
        showcase = [
            {"title": "Site", "link": "https://b.com", "screenshotpath": "/screenshots/b.jpg"},
        ]

        bundledb_path = tmp_path / "bundledb.json"
        showcase_path = tmp_path / "showcase-data.json"
        bundledb_path.write_text(json.dumps(bundledb))
        showcase_path.write_text(json.dumps(showcase))

        entries, issue_numbers = prebuild_sync.load_recent_issue_entries(
            str(bundledb_path), str(showcase_path)
        )

        assert issue_numbers == [100]
        assert len(entries) == 4
        titles = {e["Title"] for e in entries}
        assert titles == {"Blog Post", "Site", "Starter", "Release"}

    def test_single_issue_only(self, tmp_path):
        """When only one issue exists, should return just those entries."""
        bundledb = [
            {"Issue": 100, "Type": "blog post", "Title": "Only Post", "Link": "https://a.com"},
        ]

        bundledb_path = tmp_path / "bundledb.json"
        showcase_path = tmp_path / "showcase-data.json"
        bundledb_path.write_text(json.dumps(bundledb))
        showcase_path.write_text("[]")

        entries, issue_numbers = prebuild_sync.load_recent_issue_entries(
            str(bundledb_path), str(showcase_path)
        )

        assert issue_numbers == [100]
        assert len(entries) == 1
        assert entries[0]["Title"] == "Only Post"

    def test_merges_showcase_data_for_sites(self, tmp_path):
        """Site entries should get screenshotpath merged from showcase-data."""
        bundledb = [
            {"Issue": 100, "Type": "site", "Title": "Site", "Link": "https://site.com"},
        ]
        showcase = [
            {"title": "Site", "link": "https://site.com", "screenshotpath": "/screenshots/site.jpg"},
        ]

        bundledb_path = tmp_path / "bundledb.json"
        showcase_path = tmp_path / "showcase-data.json"
        bundledb_path.write_text(json.dumps(bundledb))
        showcase_path.write_text(json.dumps(showcase))

        entries, _ = prebuild_sync.load_recent_issue_entries(
            str(bundledb_path), str(showcase_path)
        )

        assert len(entries) == 1
        assert entries[0]["screenshotpath"] == "/screenshots/site.jpg"

    def test_skips_skipped_entries(self, tmp_path):
        """Entries with Skip=True should not be included."""
        bundledb = [
            {"Issue": 100, "Type": "site", "Title": "Active", "Link": "https://a.com"},
            {"Issue": 100, "Type": "site", "Title": "Skipped", "Link": "https://b.com", "Skip": True},
        ]

        bundledb_path = tmp_path / "bundledb.json"
        showcase_path = tmp_path / "showcase-data.json"
        bundledb_path.write_text(json.dumps(bundledb))
        showcase_path.write_text(json.dumps([]))

        entries, _ = prebuild_sync.load_recent_issue_entries(
            str(bundledb_path), str(showcase_path)
        )

        assert len(entries) == 1
        assert entries[0]["Title"] == "Active"

    def test_empty_bundledb(self, tmp_path):
        """Empty bundledb should return empty list."""
        bundledb_path = tmp_path / "bundledb.json"
        showcase_path = tmp_path / "showcase-data.json"
        bundledb_path.write_text("[]")
        showcase_path.write_text("[]")

        entries, issue_numbers = prebuild_sync.load_recent_issue_entries(
            str(bundledb_path), str(showcase_path)
        )

        assert entries == []
        assert issue_numbers == []


class TestCheckAndCopyAssets:
    """Tests for check_and_copy_assets()."""

    def test_copies_assets_from_both_latest_and_prior_issues(self, tmp_path):
        """Should copy assets from both latest issue and prior issue."""
        # Set up directories
        favicon_src = tmp_path / "favicons"
        favicon_dest = tmp_path / "dest_favicons"
        screenshot_src = tmp_path / "screenshots"
        screenshot_dest = tmp_path / "dest_screenshots"
        favicon_src.mkdir()
        screenshot_src.mkdir()

        # Create source files for both issues
        (favicon_src / "latest.png").write_bytes(b"latest favicon")
        (favicon_src / "prior.png").write_bytes(b"prior favicon")

        # Create bundledb with entries from two issues
        bundledb = [
            {"Issue": 100, "Type": "blog post", "Title": "Latest Post", "Link": "https://latest.com", "favicon": "/img/favicons/latest.png"},
            {"Issue": 99, "Type": "blog post", "Title": "Prior Post", "Link": "https://prior.com", "favicon": "/img/favicons/prior.png"},
            {"Issue": 98, "Type": "blog post", "Title": "Old Post", "Link": "https://old.com", "favicon": "/img/favicons/old.png"},
        ]
        bundledb_path = tmp_path / "bundledb.json"
        showcase_path = tmp_path / "showcase-data.json"
        bundledb_path.write_text(json.dumps(bundledb))
        showcase_path.write_text("[]")

        result = prebuild_sync.check_and_copy_assets(
            str(bundledb_path), str(showcase_path),
            str(favicon_src), str(favicon_dest),
            str(screenshot_src), str(screenshot_dest),
            str(tmp_path / "og-images"), str(tmp_path / "dest_og-images")
        )

        assert result["success"] is True
        assert len(result["copied"]) == 2
        assert "favicon: latest.png" in result["copied"]
        assert "favicon: prior.png" in result["copied"]
        assert (favicon_dest / "latest.png").exists()
        assert (favicon_dest / "prior.png").exists()

    def test_copies_missing_favicon(self, tmp_path):
        """Should copy favicon when missing from destination."""
        # Set up directories
        favicon_src = tmp_path / "favicons"
        favicon_dest = tmp_path / "dest_favicons"
        screenshot_src = tmp_path / "screenshots"
        screenshot_dest = tmp_path / "dest_screenshots"
        favicon_src.mkdir()
        screenshot_src.mkdir()

        # Create source favicon
        (favicon_src / "example-com.png").write_bytes(b"favicon data")

        # Create bundledb with entry
        bundledb = [
            {"Issue": 100, "Type": "blog post", "Title": "Test Post", "Link": "https://a.com", "favicon": "/img/favicons/example-com.png"},
        ]
        bundledb_path = tmp_path / "bundledb.json"
        showcase_path = tmp_path / "showcase-data.json"
        bundledb_path.write_text(json.dumps(bundledb))
        showcase_path.write_text("[]")

        result = prebuild_sync.check_and_copy_assets(
            str(bundledb_path), str(showcase_path),
            str(favicon_src), str(favicon_dest),
            str(screenshot_src), str(screenshot_dest),
            str(tmp_path / "og-images"), str(tmp_path / "dest_og-images")
        )

        assert result["success"] is True
        assert len(result["copied"]) == 1
        assert "favicon: example-com.png" in result["copied"]
        assert (favicon_dest / "example-com.png").exists()

    def test_copies_missing_screenshot_for_site(self, tmp_path):
        """Should copy screenshot when missing from destination for site entries."""
        # Set up directories
        favicon_src = tmp_path / "favicons"
        favicon_dest = tmp_path / "dest_favicons"
        screenshot_src = tmp_path / "screenshots"
        screenshot_dest = tmp_path / "dest_screenshots"
        favicon_src.mkdir()
        screenshot_src.mkdir()

        # Create source files
        (favicon_src / "site-com.png").write_bytes(b"favicon")
        (screenshot_src / "site-com-large.jpg").write_bytes(b"screenshot")

        # Create bundledb and showcase with site entry
        bundledb = [
            {"Issue": 100, "Type": "site", "Title": "Cool Site", "Link": "https://site.com", "favicon": "/img/favicons/site-com.png"},
        ]
        showcase = [
            {"title": "Cool Site", "link": "https://site.com", "screenshotpath": "/screenshots/site-com-large.jpg"},
        ]
        bundledb_path = tmp_path / "bundledb.json"
        showcase_path = tmp_path / "showcase-data.json"
        bundledb_path.write_text(json.dumps(bundledb))
        showcase_path.write_text(json.dumps(showcase))

        result = prebuild_sync.check_and_copy_assets(
            str(bundledb_path), str(showcase_path),
            str(favicon_src), str(favicon_dest),
            str(screenshot_src), str(screenshot_dest),
            str(tmp_path / "og-images"), str(tmp_path / "dest_og-images")
        )

        assert result["success"] is True
        assert len(result["copied"]) == 2
        assert "favicon: site-com.png" in result["copied"]
        assert "screenshot: site-com-large.jpg" in result["copied"]

    def test_copies_screenshot_for_starter(self, tmp_path):
        """Starters should also have screenshots copied."""
        favicon_src = tmp_path / "favicons"
        favicon_dest = tmp_path / "dest_favicons"
        screenshot_src = tmp_path / "screenshots"
        screenshot_dest = tmp_path / "dest_screenshots"
        favicon_src.mkdir()
        screenshot_src.mkdir()

        (favicon_src / "starter-com.png").write_bytes(b"favicon")
        (screenshot_src / "starter-large.jpg").write_bytes(b"screenshot")

        bundledb = [
            {"Issue": 100, "Type": "starter", "Title": "Starter", "Link": "https://github.com/starter",
             "favicon": "/img/favicons/starter-com.png", "screenshotpath": "/screenshots/starter-large.jpg"},
        ]
        bundledb_path = tmp_path / "bundledb.json"
        showcase_path = tmp_path / "showcase-data.json"
        bundledb_path.write_text(json.dumps(bundledb))
        showcase_path.write_text("[]")

        result = prebuild_sync.check_and_copy_assets(
            str(bundledb_path), str(showcase_path),
            str(favicon_src), str(favicon_dest),
            str(screenshot_src), str(screenshot_dest),
            str(tmp_path / "og-images"), str(tmp_path / "dest_og-images")
        )

        assert result["success"] is True
        assert "screenshot: starter-large.jpg" in result["copied"]

    def test_skips_existing_files(self, tmp_path):
        """Should not recopy a destination file that already matches the source."""
        import shutil as _shutil

        favicon_src = tmp_path / "favicons"
        favicon_dest = tmp_path / "dest_favicons"
        screenshot_src = tmp_path / "screenshots"
        screenshot_dest = tmp_path / "dest_screenshots"
        favicon_src.mkdir()
        favicon_dest.mkdir()
        screenshot_src.mkdir()
        screenshot_dest.mkdir()

        (favicon_src / "existing.png").write_bytes(b"source")
        _shutil.copy2(favicon_src / "existing.png", favicon_dest / "existing.png")

        bundledb = [
            {"Issue": 100, "Type": "blog post", "Title": "Post", "Link": "https://a.com", "favicon": "/img/favicons/existing.png"},
        ]
        bundledb_path = tmp_path / "bundledb.json"
        showcase_path = tmp_path / "showcase-data.json"
        bundledb_path.write_text(json.dumps(bundledb))
        showcase_path.write_text("[]")

        result = prebuild_sync.check_and_copy_assets(
            str(bundledb_path), str(showcase_path),
            str(favicon_src), str(favicon_dest),
            str(screenshot_src), str(screenshot_dest),
            str(tmp_path / "og-images"), str(tmp_path / "dest_og-images")
        )

        assert result["success"] is True
        assert result["copied"] == []
        assert result["refreshed"] == []

    def test_fails_on_missing_source(self, tmp_path):
        """Should fail if source file doesn't exist."""
        favicon_src = tmp_path / "favicons"
        favicon_dest = tmp_path / "dest_favicons"
        screenshot_src = tmp_path / "screenshots"
        screenshot_dest = tmp_path / "dest_screenshots"
        favicon_src.mkdir()
        screenshot_src.mkdir()

        # No favicon file created in source

        bundledb = [
            {"Issue": 100, "Type": "blog post", "Title": "Test Post", "Link": "https://a.com", "favicon": "/img/favicons/missing.png"},
        ]
        bundledb_path = tmp_path / "bundledb.json"
        showcase_path = tmp_path / "showcase-data.json"
        bundledb_path.write_text(json.dumps(bundledb))
        showcase_path.write_text("[]")

        result = prebuild_sync.check_and_copy_assets(
            str(bundledb_path), str(showcase_path),
            str(favicon_src), str(favicon_dest),
            str(screenshot_src), str(screenshot_dest),
            str(tmp_path / "og-images"), str(tmp_path / "dest_og-images")
        )

        assert result["success"] is False
        assert "missing.png" in result["message"]
        assert len(result["missing"]) == 1

    def test_no_entries(self, tmp_path):
        """Should return success with empty entries."""
        favicon_src = tmp_path / "favicons"
        favicon_dest = tmp_path / "dest_favicons"
        screenshot_src = tmp_path / "screenshots"
        screenshot_dest = tmp_path / "dest_screenshots"
        favicon_src.mkdir()
        screenshot_src.mkdir()

        bundledb_path = tmp_path / "bundledb.json"
        showcase_path = tmp_path / "showcase-data.json"
        bundledb_path.write_text("[]")
        showcase_path.write_text("[]")

        result = prebuild_sync.check_and_copy_assets(
            str(bundledb_path), str(showcase_path),
            str(favicon_src), str(favicon_dest),
            str(screenshot_src), str(screenshot_dest),
            str(tmp_path / "og-images"), str(tmp_path / "dest_og-images")
        )

        assert result["success"] is True
        assert result["copied"] == []

    def test_entry_without_favicon(self, tmp_path):
        """Entries without favicon field should be handled gracefully."""
        favicon_src = tmp_path / "favicons"
        favicon_dest = tmp_path / "dest_favicons"
        screenshot_src = tmp_path / "screenshots"
        screenshot_dest = tmp_path / "dest_screenshots"
        favicon_src.mkdir()
        screenshot_src.mkdir()

        bundledb = [
            {"Issue": 100, "Type": "blog post", "Title": "No Favicon", "Link": "https://a.com"},
        ]
        bundledb_path = tmp_path / "bundledb.json"
        showcase_path = tmp_path / "showcase-data.json"
        bundledb_path.write_text(json.dumps(bundledb))
        showcase_path.write_text("[]")

        result = prebuild_sync.check_and_copy_assets(
            str(bundledb_path), str(showcase_path),
            str(favicon_src), str(favicon_dest),
            str(screenshot_src), str(screenshot_dest),
            str(tmp_path / "og-images"), str(tmp_path / "dest_og-images")
        )

        assert result["success"] is True
        assert result["copied"] == []

    def test_skips_svg_icon_references(self, tmp_path):
        """SVG icon references like #icon-globe should be skipped, not treated as files."""
        favicon_src = tmp_path / "favicons"
        favicon_dest = tmp_path / "dest_favicons"
        screenshot_src = tmp_path / "screenshots"
        screenshot_dest = tmp_path / "dest_screenshots"
        favicon_src.mkdir()
        screenshot_src.mkdir()

        bundledb = [
            {"Issue": 100, "Type": "blog post", "Title": "SVG Icon Entry", "Link": "https://a.com", "favicon": "#icon-globe"},
            {"Issue": 100, "Type": "site", "Title": "Another SVG", "Link": "https://b.com", "favicon": "#icon-link"},
        ]
        bundledb_path = tmp_path / "bundledb.json"
        showcase_path = tmp_path / "showcase-data.json"
        bundledb_path.write_text(json.dumps(bundledb))
        showcase_path.write_text("[]")

        result = prebuild_sync.check_and_copy_assets(
            str(bundledb_path), str(showcase_path),
            str(favicon_src), str(favicon_dest),
            str(screenshot_src), str(screenshot_dest),
            str(tmp_path / "og-images"), str(tmp_path / "dest_og-images")
        )

        assert result["success"] is True
        assert result["copied"] == []
        assert result["missing"] == []


class TestPrebuildSyncRoute:
    """Tests for the /editor/prebuild-sync route."""

    @patch("services.prebuild_sync.sync_bundledb_repo")
    @patch("services.prebuild_sync.check_and_copy_assets")
    def test_success(self, mock_assets, mock_git, client):
        """Route should return success when both steps pass."""
        mock_git.return_value = {"success": True, "message": "Git synced"}
        mock_assets.return_value = {"success": True, "message": "Assets OK", "copied": []}

        response = client.post("/editor/prebuild-sync")
        data = response.get_json()

        assert response.status_code == 200
        assert data["success"] is True
        assert data["git_message"] == "Git synced"
        assert data["files_message"] == "Assets OK"

    @patch("services.prebuild_sync.sync_bundledb_repo")
    def test_git_failure(self, mock_git, client):
        """Route should return error when git sync fails."""
        mock_git.return_value = {"success": False, "message": "Git error"}

        response = client.post("/editor/prebuild-sync")
        data = response.get_json()

        assert response.status_code == 200
        assert data["success"] is False
        assert data["stage"] == "git"
        assert data["error"] == "Git error"

    @patch("services.prebuild_sync.sync_bundledb_repo")
    @patch("services.prebuild_sync.check_and_copy_assets")
    def test_asset_failure(self, mock_assets, mock_git, client):
        """Route should return error when asset copy fails."""
        mock_git.return_value = {"success": True, "message": "Git OK"}
        mock_assets.return_value = {"success": False, "message": "Missing file", "copied": [], "missing": ["x.png"]}

        response = client.post("/editor/prebuild-sync")
        data = response.get_json()

        assert response.status_code == 200
        assert data["success"] is False
        assert data["stage"] == "files"
        assert data["error"] == "Missing file"


def _reconcile_dirs(tmp_path):
    """Create the six source/destination dirs used by check_and_copy_assets()."""
    dirs = {
        "favicon_src": tmp_path / "favicons",
        "favicon_dest": tmp_path / "dest_favicons",
        "screenshot_src": tmp_path / "screenshots",
        "screenshot_dest": tmp_path / "dest_screenshots",
        "og_src": tmp_path / "og-images",
        "og_dest": tmp_path / "dest_og-images",
    }
    for key in ("favicon_src", "screenshot_src", "og_src"):
        dirs[key].mkdir()
    return dirs


def _run_reconcile(tmp_path, bundledb, showcase, dirs=None):
    """Write the two DB files and run check_and_copy_assets() against tmp dirs."""
    dirs = dirs or _reconcile_dirs(tmp_path)
    bundledb_path = tmp_path / "bundledb.json"
    showcase_path = tmp_path / "showcase-data.json"
    bundledb_path.write_text(json.dumps(bundledb))
    showcase_path.write_text(json.dumps(showcase))
    result = prebuild_sync.check_and_copy_assets(
        bundledb_path=str(bundledb_path),
        showcase_path=str(showcase_path),
        **{k: str(v) for k, v in dirs.items()},
    )
    return result, dirs


class TestFullDbAssetReconcile:
    """Gap 1: reconcile every asset reference in the DB, not just the recent issues."""

    def test_copies_favicon_for_old_issue_entry(self, tmp_path):
        """An entry from an issue older than the recent window still gets its favicon copied."""
        dirs = _reconcile_dirs(tmp_path)
        (dirs["favicon_src"] / "ancient.png").write_bytes(b"ancient favicon")

        bundledb = [
            {"Issue": 100, "Type": "blog post", "Title": "Latest", "Link": "https://latest.com"},
            {"Issue": 99, "Type": "blog post", "Title": "Prior", "Link": "https://prior.com"},
            {"Issue": 1, "Type": "blog post", "Title": "Ancient", "Link": "https://ancient.com",
             "favicon": "/img/favicons/ancient.png"},
        ]
        result, dirs = _run_reconcile(tmp_path, bundledb, [], dirs)

        assert result["success"] is True
        assert "favicon: ancient.png" in result["copied"]
        assert (dirs["favicon_dest"] / "ancient.png").exists()

    def test_copies_favicon_for_entry_without_issue(self, tmp_path):
        """Entries with no Issue field are invisible to an issue walk but still need assets."""
        dirs = _reconcile_dirs(tmp_path)
        (dirs["favicon_src"] / "noissue.png").write_bytes(b"favicon")

        bundledb = [
            {"Issue": 100, "Type": "blog post", "Title": "Latest", "Link": "https://latest.com"},
            {"Issue": 99, "Type": "blog post", "Title": "Prior", "Link": "https://prior.com"},
            {"Type": "blog post", "Title": "No Issue", "Link": "https://noissue.com",
             "favicon": "/img/favicons/noissue.png"},
        ]
        result, dirs = _run_reconcile(tmp_path, bundledb, [], dirs)

        assert result["success"] is True
        assert "favicon: noissue.png" in result["copied"]

    def test_copies_og_image_from_showcase_entry(self, tmp_path):
        """og-images are reconciled from showcase-data.json."""
        dirs = _reconcile_dirs(tmp_path)
        (dirs["og_src"] / "site-com-og.jpg").write_bytes(b"og image")

        showcase = [
            {"title": "Site", "link": "https://site.com", "ogImagePath": "/og-images/site-com-og.jpg"},
        ]
        result, dirs = _run_reconcile(tmp_path, [], showcase, dirs)

        assert result["success"] is True
        assert "og-image: site-com-og.jpg" in result["copied"]
        assert (dirs["og_dest"] / "site-com-og.jpg").exists()

    def test_copies_assets_for_showcase_entry_absent_from_bundledb(self, tmp_path):
        """showcase-data.json holds far more sites than bundledb; all of them need assets."""
        dirs = _reconcile_dirs(tmp_path)
        (dirs["favicon_src"] / "only-showcase.png").write_bytes(b"favicon")
        (dirs["screenshot_src"] / "only-showcase-large.jpg").write_bytes(b"screenshot")

        showcase = [
            {"title": "Showcase Only", "link": "https://only.com",
             "favicon": "/img/favicons/only-showcase.png",
             "screenshotpath": "/screenshots/only-showcase-large.jpg"},
        ]
        result, dirs = _run_reconcile(tmp_path, [], showcase, dirs)

        assert result["success"] is True
        assert "favicon: only-showcase.png" in result["copied"]
        assert "screenshot: only-showcase-large.jpg" in result["copied"]

    def test_refreshes_destination_with_different_size(self, tmp_path):
        """A destination file whose size differs from the source is stale and gets refreshed."""
        dirs = _reconcile_dirs(tmp_path)
        dirs["favicon_dest"].mkdir()
        (dirs["favicon_src"] / "stale.png").write_bytes(b"the correct new favicon bytes")
        (dirs["favicon_dest"] / "stale.png").write_bytes(b"old")

        bundledb = [
            {"Issue": 100, "Type": "blog post", "Title": "Post", "Link": "https://a.com",
             "favicon": "/img/favicons/stale.png"},
        ]
        result, dirs = _run_reconcile(tmp_path, bundledb, [], dirs)

        assert result["success"] is True
        assert "favicon: stale.png" in result["refreshed"]
        assert (dirs["favicon_dest"] / "stale.png").read_bytes() == b"the correct new favicon bytes"

    def test_refreshes_destination_older_than_source(self, tmp_path):
        """Same size but an older mtime means the source was replaced in place."""
        dirs = _reconcile_dirs(tmp_path)
        dirs["favicon_dest"].mkdir()
        src = dirs["favicon_src"] / "same-size.png"
        dest = dirs["favicon_dest"] / "same-size.png"
        src.write_bytes(b"newnewnew")
        dest.write_bytes(b"oldoldold")
        os.utime(dest, (1_000_000, 1_000_000))

        bundledb = [
            {"Issue": 100, "Type": "blog post", "Title": "Post", "Link": "https://a.com",
             "favicon": "/img/favicons/same-size.png"},
        ]
        result, dirs = _run_reconcile(tmp_path, bundledb, [], dirs)

        assert result["success"] is True
        assert "favicon: same-size.png" in result["refreshed"]
        assert dest.read_bytes() == b"newnewnew"

    def test_leaves_independently_written_destination_alone(self, tmp_path):
        """A destination newer than its source was written directly, not copied.

        capture-screenshot.js writes content/screenshots and 11tybundledb in the
        same run rather than copying between them, so ~1,300 byte-identical
        screenshots have destination mtimes newer than their sources. Those are
        not stale and must not be recopied on every build.
        """
        dirs = _reconcile_dirs(tmp_path)
        dirs["screenshot_dest"].mkdir()
        src = dirs["screenshot_src"] / "captured-large.jpg"
        dest = dirs["screenshot_dest"] / "captured-large.jpg"
        src.write_bytes(b"identical jpeg bytes")
        dest.write_bytes(b"identical jpeg bytes")
        os.utime(src, (1_000_000, 1_000_000))

        showcase = [
            {"title": "Captured", "link": "https://captured.com",
             "screenshotpath": "/screenshots/captured-large.jpg"},
        ]
        result, _ = _run_reconcile(tmp_path, [], showcase, dirs)

        assert result["success"] is True
        assert result["refreshed"] == []
        assert result["copied"] == []

    def test_leaves_matching_destination_alone(self, tmp_path):
        """A destination that matches the source in size and mtime is not touched."""
        import shutil as _shutil

        dirs = _reconcile_dirs(tmp_path)
        dirs["favicon_dest"].mkdir()
        src = dirs["favicon_src"] / "fresh.png"
        src.write_bytes(b"favicon bytes")
        _shutil.copy2(src, dirs["favicon_dest"] / "fresh.png")

        bundledb = [
            {"Issue": 100, "Type": "blog post", "Title": "Post", "Link": "https://a.com",
             "favicon": "/img/favicons/fresh.png"},
        ]
        result, dirs = _run_reconcile(tmp_path, bundledb, [], dirs)

        assert result["success"] is True
        assert result["copied"] == []
        assert result["refreshed"] == []

    def test_missing_source_for_old_entry_warns_without_failing(self, tmp_path):
        """Historical rot is reported, not a wall that blocks every build."""
        bundledb = [
            {"Issue": 100, "Type": "blog post", "Title": "Latest", "Link": "https://latest.com"},
            {"Issue": 99, "Type": "blog post", "Title": "Prior", "Link": "https://prior.com"},
            {"Issue": 1, "Type": "blog post", "Title": "Ancient", "Link": "https://ancient.com",
             "favicon": "/img/favicons/gone.png"},
        ]
        result, _ = _run_reconcile(tmp_path, bundledb, [])

        assert result["success"] is True
        assert result["missing"] == []
        assert len(result["warnings"]) == 1
        assert "gone.png" in result["warnings"][0]

    def test_missing_source_for_recent_entry_still_fails(self, tmp_path):
        """Stop-the-line is preserved for entries in the recent-issue window."""
        bundledb = [
            {"Issue": 100, "Type": "blog post", "Title": "Recent", "Link": "https://recent.com",
             "favicon": "/img/favicons/gone.png"},
        ]
        result, _ = _run_reconcile(tmp_path, bundledb, [])

        assert result["success"] is False
        assert len(result["missing"]) == 1
        assert "gone.png" in result["message"]

    def test_skips_skipped_showcase_entries(self, tmp_path):
        """showcase entries with skip: true never render, so their assets are not required."""
        showcase = [
            {"title": "Skipped", "link": "https://skipped.com", "skip": True,
             "favicon": "/img/favicons/skipped.png"},
        ]
        result, _ = _run_reconcile(tmp_path, [], showcase)

        assert result["success"] is True
        assert result["copied"] == []
        assert result["warnings"] == []

    def test_skips_skipped_old_bundledb_entries(self, tmp_path):
        """Skip: true entries from old issues are excluded too."""
        bundledb = [
            {"Issue": 100, "Type": "blog post", "Title": "Latest", "Link": "https://latest.com"},
            {"Issue": 99, "Type": "blog post", "Title": "Prior", "Link": "https://prior.com"},
            {"Issue": 1, "Type": "blog post", "Title": "Skipped", "Link": "https://a.com",
             "Skip": True, "favicon": "/img/favicons/skipped.png"},
        ]
        result, _ = _run_reconcile(tmp_path, bundledb, [])

        assert result["success"] is True
        assert result["warnings"] == []

    def test_deduplicates_shared_asset_references(self, tmp_path):
        """Many entries share one favicon; it is copied once, not once per entry."""
        dirs = _reconcile_dirs(tmp_path)
        (dirs["favicon_src"] / "shared.png").write_bytes(b"favicon")

        bundledb = [
            {"Issue": 10, "Type": "blog post", "Title": "One", "Link": "https://a.com/1",
             "favicon": "/img/favicons/shared.png"},
            {"Issue": 11, "Type": "blog post", "Title": "Two", "Link": "https://a.com/2",
             "favicon": "/img/favicons/shared.png"},
            {"Issue": 12, "Type": "blog post", "Title": "Three", "Link": "https://a.com/3",
             "favicon": "/img/favicons/shared.png"},
        ]
        result, _ = _run_reconcile(tmp_path, bundledb, [], dirs)

        assert result["success"] is True
        assert result["copied"] == ["favicon: shared.png"]
