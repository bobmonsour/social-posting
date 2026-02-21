import json
import os


def _write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)


def _read_json(path):
    with open(path) as f:
        return json.load(f)


# --- POST /editor/check-url ---

def test_check_url_match_bundledb(client, app, sample_bundledb):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    resp = client.post("/editor/check-url",
                       json={"url": "https://example.com/blog/eleventy-start"})
    data = resp.get_json()
    assert len(data["found"]) == 1
    assert data["found"][0]["source"] == "bundledb.json"
    assert data["found"][0]["title"] == "Getting Started with Eleventy"


def test_check_url_normalization(client, app, sample_bundledb):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    # With trailing slash, www prefix, no protocol
    resp = client.post("/editor/check-url",
                       json={"url": "www.example.com/blog/eleventy-start/"})
    data = resp.get_json()
    assert len(data["found"]) == 1


def test_check_url_match_showcase(client, app, sample_showcase):
    _write_json(app.config["SHOWCASE_PATH"], sample_showcase)
    resp = client.post("/editor/check-url",
                       json={"url": "https://cool11ty.dev"})
    data = resp.get_json()
    assert any(r["source"] == "showcase-data.json" for r in data["found"])


def test_check_url_no_match(client, app, sample_bundledb):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    resp = client.post("/editor/check-url",
                       json={"url": "https://nonexistent.example.com"})
    data = resp.get_json()
    assert data["found"] == []


def test_check_url_empty(client):
    resp = client.post("/editor/check-url", json={"url": ""})
    assert resp.status_code == 400


# --- GET /editor/data ---

def test_editor_data_merges_showcase(client, app, sample_bundledb, sample_showcase):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    _write_json(app.config["SHOWCASE_PATH"], sample_showcase)
    resp = client.get("/editor/data")
    data = resp.get_json()["bundledb"]
    site = next(e for e in data if e["Type"] == "site")
    assert site["screenshotpath"] == "/screenshots/cool11ty-dev.jpg"
    assert site["leaderboardLink"] == "https://www.11ty.dev/speedlify/cool11ty-dev/"


def test_editor_data_no_showcase_match(client, app, sample_bundledb):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    _write_json(app.config["SHOWCASE_PATH"], [])
    resp = client.get("/editor/data")
    data = resp.get_json()["bundledb"]
    site = next(e for e in data if e["Type"] == "site")
    assert "screenshotpath" not in site


# --- POST /editor/save (create) ---

def test_editor_save_create_blog_post(client, app):
    item = {
        "Issue": 101,
        "Type": "blog post",
        "Title": "New Post",
        "Link": "https://example.com/new",
        "Date": "2026-02-20",
        "Author": "Test",
        "Categories": [],
        "formattedDate": "February 20, 2026",
        "description": "A new post",
    }
    resp = client.post("/editor/save", json={"item": item, "create": True})
    data = resp.get_json()
    assert data["success"]
    assert data["new_index"] == 0

    saved = _read_json(app.config["BUNDLEDB_PATH"])
    assert len(saved) == 1
    assert saved[0]["Title"] == "New Post"


def test_editor_save_create_site(client, app, monkeypatch):
    import services.bwe_list as bwe_list
    bwe_path = os.path.join(os.path.dirname(app.config["BUNDLEDB_PATH"]), "bwe.md")
    with open(bwe_path, "w") as f:
        f.write("- TO BE POSTED -\n\n- ALREADY POSTED -\n")
    monkeypatch.setattr(bwe_list, "BWE_FILE", bwe_path)

    item = {
        "Issue": 101,
        "Type": "site",
        "Title": "New Site",
        "Link": "https://newsite.dev",
        "Date": "2026-02-20",
        "formattedDate": "February 20, 2026",
        "description": "A new site",
        "favicon": "/img/fav.png",
        "screenshotpath": "/screenshots/new.jpg",
        "leaderboardLink": "",
    }
    resp = client.post("/editor/save", json={"item": item, "create": True})
    data = resp.get_json()
    assert data["success"]
    assert data.get("bwe_added")
    assert data.get("showcase_added")

    # screenshotpath should not be in bundledb
    saved = _read_json(app.config["BUNDLEDB_PATH"])
    assert "screenshotpath" not in saved[0]

    # showcase-data should have the entry
    showcase = _read_json(app.config["SHOWCASE_PATH"])
    assert len(showcase) == 1
    assert showcase[0]["title"] == "New Site"
    assert showcase[0]["screenshotpath"] == "/screenshots/new.jpg"


def test_editor_save_creates_backup(client, app):
    item = {"Type": "release", "Title": "v1", "Link": "https://x.com/v1", "Date": "2026-01-01"}
    resp = client.post("/editor/save", json={"item": item, "create": True})
    data = resp.get_json()
    assert data["backup_created"]
    backups = os.listdir(app.config["BUNDLEDB_BACKUP_DIR"])
    assert len(backups) == 1


def test_editor_save_no_duplicate_backup(client, app):
    item = {"Type": "release", "Title": "v1", "Link": "https://x.com/v1", "Date": "2026-01-01"}
    client.post("/editor/save", json={"item": item, "create": True})
    # Second save with backup_created=True
    item2 = {"Type": "release", "Title": "v2", "Link": "https://x.com/v2", "Date": "2026-01-02"}
    client.post("/editor/save", json={"item": item2, "create": True, "backup_created": True})
    backups = os.listdir(app.config["BUNDLEDB_BACKUP_DIR"])
    assert len(backups) == 1


# --- POST /editor/save (edit) ---

def test_editor_save_edit(client, app, sample_bundledb):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    edited = sample_bundledb[0].copy()
    edited["Title"] = "Updated Title"
    resp = client.post("/editor/save", json={"item": edited, "index": 0})
    data = resp.get_json()
    assert data["success"]
    saved = _read_json(app.config["BUNDLEDB_PATH"])
    assert saved[0]["Title"] == "Updated Title"


def test_editor_save_edit_site_syncs_showcase(client, app, sample_bundledb, sample_showcase):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    _write_json(app.config["SHOWCASE_PATH"], sample_showcase)
    edited = sample_bundledb[1].copy()
    edited["Title"] = "Updated Site"
    edited["screenshotpath"] = "/screenshots/updated.jpg"
    edited["leaderboardLink"] = ""
    resp = client.post("/editor/save", json={"item": edited, "index": 1})
    data = resp.get_json()
    assert data.get("showcase_updated")
    showcase = _read_json(app.config["SHOWCASE_PATH"])
    assert showcase[0]["title"] == "Updated Site"
    assert showcase[0]["screenshotpath"] == "/screenshots/updated.jpg"


def test_editor_save_edit_propagation(client, app):
    data = [
        {"Type": "blog post", "Title": "Post 1", "Author": "Alice", "favicon": ""},
        {"Type": "blog post", "Title": "Post 2", "Author": "Alice", "favicon": ""},
    ]
    _write_json(app.config["BUNDLEDB_PATH"], data)
    edited = data[0].copy()
    edited["favicon"] = "/img/alice.png"
    resp = client.post("/editor/save", json={
        "item": edited,
        "index": 0,
        "propagate": [{"index": 1, "field": "favicon", "value": "/img/alice.png"}],
    })
    result = resp.get_json()
    assert result["propagated"] == 1
    saved = _read_json(app.config["BUNDLEDB_PATH"])
    assert saved[1]["favicon"] == "/img/alice.png"


def test_editor_save_edit_invalid_index(client, app, sample_bundledb):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    resp = client.post("/editor/save", json={"item": sample_bundledb[0], "index": 99})
    assert resp.status_code == 400


# --- POST /editor/delete ---

def test_editor_delete(client, app, sample_bundledb):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    resp = client.post("/editor/delete", json={"index": 2})
    data = resp.get_json()
    assert data["success"]
    saved = _read_json(app.config["BUNDLEDB_PATH"])
    assert len(saved) == len(sample_bundledb) - 1


def test_editor_delete_site_removes_showcase(client, app, sample_bundledb, sample_showcase):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    _write_json(app.config["SHOWCASE_PATH"], sample_showcase)
    # Index 1 is the site entry
    resp = client.post("/editor/delete", json={"index": 1})
    assert resp.get_json()["success"]
    showcase = _read_json(app.config["SHOWCASE_PATH"])
    assert len(showcase) == 0


def test_editor_delete_invalid_index(client, app, sample_bundledb):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    resp = client.post("/editor/delete", json={"index": 99})
    assert resp.status_code == 400


# --- POST /editor/delete-test-entries ---

def test_delete_test_entries(client, app):
    data = [
        {"Title": "Real Entry", "Type": "blog post"},
        {"Title": "bobdemo99 test", "Type": "blog post"},
        {"Title": "Another bobdemo99", "Type": "site", "Link": "https://bobdemo99.dev"},
    ]
    showcase = [
        {"title": "Another bobdemo99", "link": "https://bobdemo99.dev"},
        {"title": "Real Showcase", "link": "https://real.dev"},
    ]
    _write_json(app.config["BUNDLEDB_PATH"], data)
    _write_json(app.config["SHOWCASE_PATH"], showcase)

    resp = client.post("/editor/delete-test-entries", json={})
    result = resp.get_json()
    assert result["success"]
    assert result["deleted"] == 2

    saved = _read_json(app.config["BUNDLEDB_PATH"])
    assert len(saved) == 1
    assert saved[0]["Title"] == "Real Entry"

    sc = _read_json(app.config["SHOWCASE_PATH"])
    assert len(sc) == 1
    assert sc[0]["title"] == "Real Showcase"


def test_delete_test_entries_none_found(client, app, sample_bundledb):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    resp = client.post("/editor/delete-test-entries", json={})
    result = resp.get_json()
    assert result["deleted"] == 0
