import json
import os

from services.issue_counts import get_latest_issue_counts


def _setup_blog(tmp_path, issues):
    """Create blog post files for the given issue numbers."""
    for n in issues:
        year = "2024" if n < 50 else "2025"
        year_dir = tmp_path / year
        year_dir.mkdir(parents=True, exist_ok=True)
        (year_dir / f"11ty-bundle-{n}.md").write_text("")
    return str(tmp_path)


def _setup_bundledb(tmp_path, entries):
    """Write a bundledb.json file and return its path."""
    path = tmp_path / "bundledb.json"
    path.write_text(json.dumps(entries))
    return str(path)


def test_next_issue_from_blog(tmp_path, monkeypatch):
    blog_path = _setup_blog(tmp_path / "blog", [80, 85, 86])
    db_path = _setup_bundledb(tmp_path, [])
    monkeypatch.setattr("services.issue_counts.BUNDLEDB_PATH", db_path)

    result = get_latest_issue_counts(blog_path=blog_path)
    assert result["issue_number"] == 87


def test_counts_for_next_issue(tmp_path, monkeypatch):
    blog_path = _setup_blog(tmp_path / "blog", [85, 86])
    entries = [
        {"Issue": "87", "Type": "blog post"},
        {"Issue": "87", "Type": "site"},
        {"Issue": "87", "Type": "site"},
        {"Issue": "87", "Type": "release"},
        {"Issue": "86", "Type": "blog post"},
    ]
    db_path = _setup_bundledb(tmp_path, entries)
    monkeypatch.setattr("services.issue_counts.BUNDLEDB_PATH", db_path)

    result = get_latest_issue_counts(blog_path=blog_path)
    assert result["issue_number"] == 87
    assert result["blog_posts"] == 1
    assert result["sites"] == 2
    assert result["releases"] == 1
    assert result["starters"] == 0


def test_skipped_entries_excluded(tmp_path, monkeypatch):
    blog_path = _setup_blog(tmp_path / "blog", [86])
    entries = [
        {"Issue": "87", "Type": "blog post"},
        {"Issue": "87", "Type": "blog post", "Skip": True},
    ]
    db_path = _setup_bundledb(tmp_path, entries)
    monkeypatch.setattr("services.issue_counts.BUNDLEDB_PATH", db_path)

    result = get_latest_issue_counts(blog_path=blog_path)
    assert result["blog_posts"] == 1


def test_no_blog_files_returns_none(tmp_path, monkeypatch):
    blog_path = str(tmp_path / "empty_blog")
    os.makedirs(blog_path)
    db_path = _setup_bundledb(tmp_path, [])
    monkeypatch.setattr("services.issue_counts.BUNDLEDB_PATH", db_path)

    result = get_latest_issue_counts(blog_path=blog_path)
    assert result is None


def test_missing_blog_dir_returns_none(tmp_path, monkeypatch):
    result = get_latest_issue_counts(blog_path=str(tmp_path / "nonexistent"))
    assert result is None


def test_missing_bundledb_returns_zero_counts(tmp_path, monkeypatch):
    blog_path = _setup_blog(tmp_path / "blog", [86])
    monkeypatch.setattr("services.issue_counts.BUNDLEDB_PATH", str(tmp_path / "nope.json"))

    result = get_latest_issue_counts(blog_path=blog_path)
    assert result["issue_number"] == 87
    assert result["blog_posts"] == 0


def test_non_matching_files_ignored(tmp_path, monkeypatch):
    blog_path = tmp_path / "blog"
    year_dir = blog_path / "2025"
    year_dir.mkdir(parents=True)
    (year_dir / "11ty-bundle-86.md").write_text("")
    (year_dir / "some-other-post.md").write_text("")
    (year_dir / "11ty-bundle-foo.md").write_text("")
    db_path = _setup_bundledb(tmp_path, [])
    monkeypatch.setattr("services.issue_counts.BUNDLEDB_PATH", db_path)

    result = get_latest_issue_counts(blog_path=str(blog_path))
    assert result["issue_number"] == 87
