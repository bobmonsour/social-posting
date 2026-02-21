import json
import os


def _write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)


def _read_json(path):
    with open(path) as f:
        return json.load(f)


# --- Round-trip blog post ---

def test_round_trip_blog_post(client, app):
    item = {
        "Issue": 101,
        "Type": "blog post",
        "Title": "Round Trip Post",
        "Link": "https://example.com/rt",
        "Date": "2026-02-20",
        "Author": "RT Author",
        "Categories": ["Testing"],
        "formattedDate": "February 20, 2026",
        "slugifiedAuthor": "rt-author",
        "slugifiedTitle": "round-trip-post",
        "description": "Testing round trip",
        "AuthorSite": "https://example.com",
        "AuthorSiteDescription": "A blog",
        "favicon": "/img/fav.png",
        "rssLink": "https://example.com/feed.xml",
        "socialLinks": {"mastodon": "@rt@mastodon.social", "bluesky": "@rt.bsky.social"},
    }
    client.post("/editor/save", json={"item": item, "create": True})
    resp = client.get("/editor/data")
    data = resp.get_json()
    assert len(data) == 1
    saved = data[0]
    for key in ("Issue", "Type", "Title", "Link", "Date", "Author", "Categories",
                "formattedDate", "description", "favicon", "rssLink"):
        assert saved[key] == item[key], f"Mismatch on {key}"
    assert saved["socialLinks"]["mastodon"] == "@rt@mastodon.social"


# --- Round-trip site with showcase merge ---

def test_round_trip_site(client, app, monkeypatch):
    import services.bwe_list as bwe_list
    bwe_path = os.path.join(os.path.dirname(app.config["BUNDLEDB_PATH"]), "bwe.md")
    with open(bwe_path, "w") as f:
        f.write("- TO BE POSTED -\n\n- ALREADY POSTED -\n")
    monkeypatch.setattr(bwe_list, "BWE_FILE", bwe_path)

    item = {
        "Issue": 101,
        "Type": "site",
        "Title": "RT Site",
        "Link": "https://rtsite.dev",
        "Date": "2026-02-20",
        "formattedDate": "February 20, 2026",
        "description": "A round trip site",
        "favicon": "/img/rt.png",
        "screenshotpath": "/screenshots/rt.jpg",
        "leaderboardLink": "https://www.11ty.dev/speedlify/rtsite-dev/",
    }
    client.post("/editor/save", json={"item": item, "create": True})

    resp = client.get("/editor/data")
    data = resp.get_json()
    site = data[0]
    assert site["Title"] == "RT Site"
    # screenshotpath should come from showcase merge
    assert site["screenshotpath"] == "/screenshots/rt.jpg"
    assert site["leaderboardLink"] == "https://www.11ty.dev/speedlify/rtsite-dev/"

    # Verify screenshotpath NOT in bundledb file directly
    raw = _read_json(app.config["BUNDLEDB_PATH"])
    assert "screenshotpath" not in raw[0]


# --- Schema validation ---

def test_schema_blog_post_required_fields(client, app):
    item = {
        "Issue": 1, "Type": "blog post", "Title": "T", "Link": "https://x.com",
        "Date": "2026-01-01", "Author": "A", "Categories": [],
        "formattedDate": "Jan 1", "description": "D",
    }
    client.post("/editor/save", json={"item": item, "create": True})
    saved = _read_json(app.config["BUNDLEDB_PATH"])[0]
    for field in ("Issue", "Type", "Title", "Link", "Date", "Author"):
        assert field in saved


def test_schema_site_required_fields(client, app, monkeypatch):
    import services.bwe_list as bwe_list
    bwe_path = os.path.join(os.path.dirname(app.config["BUNDLEDB_PATH"]), "bwe.md")
    with open(bwe_path, "w") as f:
        f.write("- TO BE POSTED -\n\n- ALREADY POSTED -\n")
    monkeypatch.setattr(bwe_list, "BWE_FILE", bwe_path)

    item = {
        "Issue": 1, "Type": "site", "Title": "S", "Link": "https://s.dev",
        "Date": "2026-01-01", "formattedDate": "Jan 1", "description": "D",
        "favicon": "", "screenshotpath": "", "leaderboardLink": "",
    }
    client.post("/editor/save", json={"item": item, "create": True})
    saved = _read_json(app.config["BUNDLEDB_PATH"])[0]
    for field in ("Issue", "Type", "Title", "Link", "Date"):
        assert field in saved


# --- Showcase-data sync ---

def test_showcase_sync_on_edit(client, app, sample_bundledb, sample_showcase):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    _write_json(app.config["SHOWCASE_PATH"], sample_showcase)

    edited = sample_bundledb[1].copy()
    edited["Title"] = "Synced Title"
    edited["description"] = "Synced desc"
    edited["screenshotpath"] = "/screenshots/synced.jpg"
    edited["leaderboardLink"] = ""
    client.post("/editor/save", json={"item": edited, "index": 1})

    showcase = _read_json(app.config["SHOWCASE_PATH"])
    assert showcase[0]["title"] == "Synced Title"
    assert showcase[0]["description"] == "Synced desc"
    assert showcase[0]["screenshotpath"] == "/screenshots/synced.jpg"


# --- History format ---

def test_history_draft_format(client, app):
    client.post("/post", data={"text": "Draft entry", "is_draft": "on"})
    history = _read_json(app.config["HISTORY_FILE"])
    entry = history[0]
    assert entry["is_draft"] is True
    assert "id" in entry
    assert "timestamp" in entry
    assert isinstance(entry["images"], list)
    assert entry["platforms"] == []


# --- Backup creation ---

def test_backup_first_save_only(client, app):
    item1 = {"Type": "release", "Title": "v1", "Link": "https://x.com/v1", "Date": "2026-01-01"}
    resp1 = client.post("/editor/save", json={"item": item1, "create": True})
    assert resp1.get_json()["backup_created"]

    item2 = {"Type": "release", "Title": "v2", "Link": "https://x.com/v2", "Date": "2026-01-02"}
    resp2 = client.post("/editor/save", json={"item": item2, "create": True, "backup_created": True})
    assert resp2.get_json()["backup_created"]

    backups = os.listdir(app.config["BUNDLEDB_BACKUP_DIR"])
    assert len(backups) == 1
