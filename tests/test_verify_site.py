import json

from services import verify_site


def _write_db(tmp_path, monkeypatch, entries):
    path = tmp_path / "bundledb.json"
    path.write_text(json.dumps(entries))
    monkeypatch.setattr(verify_site, "BUNDLEDB_PATH", path)


DB = [
    {"Issue": 93, "Type": "blog post", "Title": "Published"},
    {"Issue": 94, "Type": "blog post", "Title": "Current"},
    {"Issue": 94, "Type": "starter", "Title": "Starter"},
    {"Issue": 95, "Type": "site", "Title": "Queued"},
    {"Issue": 96, "Type": "site", "Title": "Skipped", "Skip": True},
    {"Issue": 96, "Type": "site", "Title": "Queued later"},
]


def test_latest_issue_defaults_to_max_issue(tmp_path, monkeypatch):
    _write_db(tmp_path, monkeypatch, DB)

    entries, label = verify_site.load_entries_by_latest_issue()

    assert [e["Title"] for e in entries] == ["Queued later"]
    assert label == "96"


def test_from_issue_includes_every_issue_from_that_point(tmp_path, monkeypatch):
    _write_db(tmp_path, monkeypatch, DB)

    entries, label = verify_site.load_entries_by_latest_issue(from_issue=94)

    assert [e["Title"] for e in entries] == ["Current", "Queued", "Queued later"]
    assert label == "94–96"


def test_from_issue_equal_to_max_issue(tmp_path, monkeypatch):
    _write_db(tmp_path, monkeypatch, DB)

    _, label = verify_site.load_entries_by_latest_issue(from_issue=96)

    assert label == "96"
