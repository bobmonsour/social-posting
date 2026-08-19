import json
import os
import subprocess

import pytest

import app as app_module
from services import showcase_output


@pytest.fixture
def showcase_dir(tmp_path, monkeypatch):
    """A stand-in for 11tybundle.dev/_site/showcase."""
    path = tmp_path / "_site" / "showcase"
    path.mkdir(parents=True)
    monkeypatch.setattr(showcase_output, "SHOWCASE_OUTPUT_DIR", path)
    return path


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
    resp = client.post("/editor/save", json={"item": edited, "link": sample_bundledb[0]["Link"]})
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
    resp = client.post("/editor/save", json={"item": edited, "link": sample_bundledb[1]["Link"]})
    data = resp.get_json()
    assert data.get("showcase_updated")
    showcase = _read_json(app.config["SHOWCASE_PATH"])
    assert showcase[0]["title"] == "Updated Site"
    assert showcase[0]["screenshotpath"] == "/screenshots/updated.jpg"


def test_editor_save_edit_propagation(client, app):
    data = [
        {"Type": "blog post", "Title": "Post 1", "Author": "Alice", "Link": "https://example.com/post1", "favicon": ""},
        {"Type": "blog post", "Title": "Post 2", "Author": "Alice", "Link": "https://example.com/post2", "favicon": ""},
    ]
    _write_json(app.config["BUNDLEDB_PATH"], data)
    edited = data[0].copy()
    edited["favicon"] = "/img/alice.png"
    resp = client.post("/editor/save", json={
        "item": edited,
        "link": "https://example.com/post1",
        "propagate": [{"link": "https://example.com/post2", "field": "favicon", "value": "/img/alice.png"}],
    })
    result = resp.get_json()
    assert result["propagated"] == 1
    saved = _read_json(app.config["BUNDLEDB_PATH"])
    assert saved[1]["favicon"] == "/img/alice.png"


def test_editor_save_edit_not_found(client, app, sample_bundledb):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    resp = client.post("/editor/save", json={"item": sample_bundledb[0], "link": "https://nonexistent.example.com"})
    assert resp.status_code == 404


# --- POST /editor/save (ogImagePath persistence) ---

def test_editor_save_create_site_persists_og_image_path(client, app, monkeypatch):
    import services.bwe_list as bwe_list
    bwe_path = os.path.join(os.path.dirname(app.config["BUNDLEDB_PATH"]), "bwe.md")
    with open(bwe_path, "w") as f:
        f.write("- TO BE POSTED -\n\n- ALREADY POSTED -\n")
    monkeypatch.setattr(bwe_list, "BWE_FILE", bwe_path)

    item = {
        "Type": "site",
        "Title": "OG Test Site",
        "Link": "https://og-test.dev",
        "Date": "2026-02-20",
        "formattedDate": "February 20, 2026",
        "description": "OG derivation test",
        "favicon": "/img/fav.png",
        "screenshotpath": "/screenshots/og-test-dev-large.jpg",
        "leaderboardLink": "",
    }
    resp = client.post("/editor/save", json={"item": item, "create": True})
    assert resp.get_json()["success"]

    showcase = _read_json(app.config["SHOWCASE_PATH"])
    assert showcase[0]["screenshotpath"] == "/screenshots/og-test-dev-large.jpg"
    assert showcase[0]["ogImagePath"] == "/og-images/og-test-dev-og.jpg"


def test_editor_save_edit_site_persists_og_image_path(client, app, sample_bundledb):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    showcase = [{
        "title": "Cool Eleventy Site",
        "link": "https://cool11ty.dev",
        "screenshotpath": "/screenshots/old-large.jpg",
        "ogImagePath": "/og-images/old-og.jpg",
    }]
    _write_json(app.config["SHOWCASE_PATH"], showcase)

    edited = sample_bundledb[1].copy()
    edited["screenshotpath"] = "/screenshots/cool11ty-dev-large.jpg"
    edited["leaderboardLink"] = ""
    resp = client.post("/editor/save",
                       json={"item": edited, "link": sample_bundledb[1]["Link"]})
    assert resp.get_json()["success"]

    saved = _read_json(app.config["SHOWCASE_PATH"])
    assert saved[0]["screenshotpath"] == "/screenshots/cool11ty-dev-large.jpg"
    assert saved[0]["ogImagePath"] == "/og-images/cool11ty-dev-og.jpg"


def test_editor_save_showcase_only_persists_og_image_path(client, app):
    showcase = [{
        "title": "Showcase Only",
        "link": "https://showcase-only.dev",
        "description": "old desc",
        "date": "2026-01-01",
        "formattedDate": "Jan 1, 2026",
        "favicon": "/fav.png",
        "screenshotpath": "/screenshots/old-large.jpg",
        "leaderboardLink": "",
    }]
    _write_json(app.config["SHOWCASE_PATH"], showcase)

    edited = {
        "Title": "Showcase Only",
        "Link": "https://showcase-only.dev",
        "Date": "2026-02-01",
        "formattedDate": "Feb 1, 2026",
        "description": "new desc",
        "favicon": "/fav.png",
        "screenshotpath": "/screenshots/showcase-only-dev-large.jpg",
        "leaderboardLink": "",
    }
    resp = client.post("/editor/save", json={
        "item": edited,
        "link": "https://showcase-only.dev",
        "showcase_only": True,
    })
    assert resp.get_json()["success"]

    saved = _read_json(app.config["SHOWCASE_PATH"])
    assert saved[0]["screenshotpath"] == "/screenshots/showcase-only-dev-large.jpg"
    assert saved[0]["ogImagePath"] == "/og-images/showcase-only-dev-og.jpg"


# --- POST /editor/delete-preview ---

def test_delete_preview_site_lists_all_three_targets(client, app, sample_bundledb,
                                                     sample_showcase, showcase_dir):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    _write_json(app.config["SHOWCASE_PATH"], sample_showcase)
    (showcase_dir / "cool11ty-dev").mkdir()

    plan = client.post("/editor/delete-preview",
                       json={"link": "https://cool11ty.dev"}).get_json()

    assert plan["bundledb"]["status"] == "delete"
    assert plan["bundledb"]["title"] == "Cool Eleventy Site"
    assert plan["bundledb"]["type"] == "site"
    assert plan["bundledb"]["issue"] == 100
    assert plan["showcase"]["status"] == "delete"
    assert plan["showcase"]["title"] == "Cool Eleventy Site"
    assert plan["showcase_output"]["status"] == "delete"
    assert plan["showcase_output"]["slug"] == "cool11ty-dev"


def test_delete_preview_reports_absent_build_output(client, app, sample_bundledb,
                                                    sample_showcase, showcase_dir):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    _write_json(app.config["SHOWCASE_PATH"], sample_showcase)
    # no directory created in showcase_dir

    plan = client.post("/editor/delete-preview",
                       json={"link": "https://cool11ty.dev"}).get_json()

    assert plan["showcase_output"]["status"] == "none"
    assert plan["showcase_output"]["slug"] == "cool11ty-dev"


def test_delete_preview_blog_post_marks_showcase_not_applicable(client, app,
                                                                sample_bundledb,
                                                                showcase_dir):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)

    plan = client.post("/editor/delete-preview",
                       json={"link": sample_bundledb[0]["Link"]}).get_json()

    assert plan["bundledb"]["status"] == "delete"
    assert plan["bundledb"]["type"] == "blog post"
    assert plan["showcase"]["status"] == "n/a"
    assert plan["showcase_output"]["status"] == "n/a"


def test_delete_preview_showcase_only_leaves_bundledb_alone(client, app, showcase_dir):
    _write_json(app.config["SHOWCASE_PATH"],
                [{"title": "Delete Me", "link": "https://delete.dev"}])
    (showcase_dir / "delete-dev").mkdir()

    plan = client.post("/editor/delete-preview",
                       json={"showcase_only": True,
                             "link": "https://delete.dev"}).get_json()

    assert plan["bundledb"]["status"] == "n/a"
    assert plan["showcase"]["status"] == "delete"
    assert plan["showcase"]["title"] == "Delete Me"
    assert plan["showcase_output"]["status"] == "delete"


def test_delete_preview_site_missing_from_showcase_data(client, app, sample_bundledb,
                                                        showcase_dir):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    _write_json(app.config["SHOWCASE_PATH"], [])

    plan = client.post("/editor/delete-preview",
                       json={"link": "https://cool11ty.dev"}).get_json()

    assert plan["bundledb"]["status"] == "delete"
    assert plan["showcase"]["status"] == "none"


def test_delete_preview_normalizes_a_blank_issue_to_none(client, app, sample_bundledb):
    entry = dict(sample_bundledb[0], Issue="")
    _write_json(app.config["BUNDLEDB_PATH"], [entry])

    plan = client.post("/editor/delete-preview",
                       json={"link": entry["Link"]}).get_json()

    assert plan["bundledb"]["issue"] is None


def test_delete_preview_unknown_link_is_404(client, app, sample_bundledb):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    resp = client.post("/editor/delete-preview",
                       json={"link": "https://nonexistent.example.com"})
    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


def test_delete_preview_showcase_only_unknown_link_is_404(client, app):
    _write_json(app.config["SHOWCASE_PATH"], [])
    resp = client.post("/editor/delete-preview",
                       json={"showcase_only": True, "link": "https://nope.dev"})
    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


def test_delete_preview_does_not_modify_anything(client, app, sample_bundledb,
                                                 sample_showcase, showcase_dir):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    _write_json(app.config["SHOWCASE_PATH"], sample_showcase)
    page = showcase_dir / "cool11ty-dev"
    page.mkdir()

    client.post("/editor/delete-preview", json={"link": "https://cool11ty.dev"})

    assert _read_json(app.config["BUNDLEDB_PATH"]) == sample_bundledb
    assert _read_json(app.config["SHOWCASE_PATH"]) == sample_showcase
    assert page.exists()


def test_delete_preview_matches_what_delete_actually_does(client, app, sample_bundledb,
                                                          sample_showcase, showcase_dir):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    _write_json(app.config["SHOWCASE_PATH"], sample_showcase)
    (showcase_dir / "cool11ty-dev").mkdir()

    plan = client.post("/editor/delete-preview",
                       json={"link": "https://cool11ty.dev"}).get_json()
    client.post("/editor/delete", json={"link": "https://cool11ty.dev"})

    bundledb = _read_json(app.config["BUNDLEDB_PATH"])
    showcase = _read_json(app.config["SHOWCASE_PATH"])
    assert (plan["bundledb"]["status"] == "delete") == (len(bundledb) == len(sample_bundledb) - 1)
    assert (plan["showcase"]["status"] == "delete") == (len(showcase) == len(sample_showcase) - 1)
    assert (plan["showcase_output"]["status"] == "delete") == (not (showcase_dir / "cool11ty-dev").exists())


# --- POST /editor/delete ---

def test_editor_delete(client, app, sample_bundledb):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    resp = client.post("/editor/delete", json={"link": sample_bundledb[2]["Link"]})
    data = resp.get_json()
    assert data["success"]
    saved = _read_json(app.config["BUNDLEDB_PATH"])
    assert len(saved) == len(sample_bundledb) - 1


def test_editor_delete_site_removes_showcase(client, app, sample_bundledb, sample_showcase):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    _write_json(app.config["SHOWCASE_PATH"], sample_showcase)
    resp = client.post("/editor/delete", json={"link": sample_bundledb[1]["Link"]})
    assert resp.get_json()["success"]
    showcase = _read_json(app.config["SHOWCASE_PATH"])
    assert len(showcase) == 0


def test_editor_delete_not_found(client, app, sample_bundledb):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    resp = client.post("/editor/delete", json={"link": "https://nonexistent.example.com"})
    assert resp.status_code == 404


def test_editor_delete_site_removes_build_output(client, app, sample_bundledb,
                                                 sample_showcase, showcase_dir):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    _write_json(app.config["SHOWCASE_PATH"], sample_showcase)
    page = showcase_dir / "cool11ty-dev"
    page.mkdir()
    (page / "index.html").write_text("<html></html>")

    resp = client.post("/editor/delete", json={"link": sample_bundledb[1]["Link"]})

    data = resp.get_json()
    assert data["success"]
    assert data["showcase_output"]["status"] == "deleted"
    assert data["showcase_output"]["slug"] == "cool11ty-dev"
    assert not page.exists()


def test_editor_delete_blog_post_leaves_build_output_alone(client, app, sample_bundledb,
                                                           showcase_dir):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    # A site with the same hostname as the blog post being deleted
    page = showcase_dir / "example-com"
    page.mkdir()

    resp = client.post("/editor/delete", json={"link": sample_bundledb[0]["Link"]})

    assert resp.get_json()["success"]
    assert resp.get_json().get("showcase_output") is None
    assert page.exists()


# --- GET /editor/data (origin tags + showcase_only) ---

def test_editor_data_origin_tags(client, app, sample_bundledb, sample_showcase):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    _write_json(app.config["SHOWCASE_PATH"], sample_showcase)
    resp = client.get("/editor/data")
    data = resp.get_json()
    bundledb = data["bundledb"]
    # Blog post should be "bundledb" origin
    blog = next(e for e in bundledb if e["Type"] == "blog post")
    assert blog["_origin"] == "bundledb"
    # Site in both files should be "both"
    site = next(e for e in bundledb if e["Type"] == "site")
    assert site["_origin"] == "both"


def test_editor_data_showcase_only(client, app, sample_bundledb):
    showcase = [
        {"title": "Cool Eleventy Site", "link": "https://cool11ty.dev",
         "description": "in both", "date": "2026-01-10"},
        {"title": "Orphan Site", "link": "https://orphan.dev",
         "description": "showcase only", "date": "2026-01-05",
         "formattedDate": "Jan 5, 2026", "favicon": "/fav.png",
         "screenshotpath": "/ss.jpg", "leaderboardLink": ""},
    ]
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    _write_json(app.config["SHOWCASE_PATH"], showcase)
    resp = client.get("/editor/data")
    data = resp.get_json()
    sc_only = data["showcase_only"]
    assert len(sc_only) == 1
    assert sc_only[0]["Title"] == "Orphan Site"
    assert sc_only[0]["Link"] == "https://orphan.dev"
    assert sc_only[0]["Type"] == "site"
    assert sc_only[0]["_origin"] == "showcase"
    assert sc_only[0]["_showcaseIndex"] == 1


def test_editor_data_showcase_only_with_skip(client, app):
    showcase = [
        {"title": "Skipped Site", "link": "https://skip.dev", "Skip": True},
    ]
    _write_json(app.config["BUNDLEDB_PATH"], [])
    _write_json(app.config["SHOWCASE_PATH"], showcase)
    resp = client.get("/editor/data")
    sc_only = resp.get_json()["showcase_only"]
    assert sc_only[0]["Skip"] is True


# --- POST /editor/save (showcase-only) ---

def test_editor_save_showcase_only(client, app):
    showcase = [
        {"title": "Old Title", "link": "https://old.dev", "description": "old",
         "date": "2026-01-01", "formattedDate": "Jan 1, 2026",
         "favicon": "", "screenshotpath": "", "leaderboardLink": ""},
    ]
    _write_json(app.config["SHOWCASE_PATH"], showcase)
    item = {
        "Title": "New Title", "Link": "https://old.dev", "Date": "2026-01-01",
        "formattedDate": "Jan 1, 2026", "description": "updated",
        "favicon": "/fav.png", "screenshotpath": "/ss.jpg", "leaderboardLink": "",
    }
    resp = client.post("/editor/save", json={
        "item": item, "showcase_only": True, "link": "https://old.dev"
    })
    assert resp.get_json()["success"]
    saved = _read_json(app.config["SHOWCASE_PATH"])
    assert saved[0]["title"] == "New Title"
    assert saved[0]["description"] == "updated"
    assert saved[0]["favicon"] == "/fav.png"


def test_editor_save_showcase_only_skip(client, app):
    showcase = [
        {"title": "Site", "link": "https://site.dev", "description": ""},
    ]
    _write_json(app.config["SHOWCASE_PATH"], showcase)
    item = {"Title": "Site", "Link": "https://site.dev", "Skip": True}
    resp = client.post("/editor/save", json={
        "item": item, "showcase_only": True, "link": "https://site.dev"
    })
    assert resp.get_json()["success"]
    saved = _read_json(app.config["SHOWCASE_PATH"])
    assert saved[0]["Skip"] is True


def test_editor_save_showcase_only_remove_skip(client, app):
    showcase = [
        {"title": "Site", "link": "https://site.dev", "Skip": True},
    ]
    _write_json(app.config["SHOWCASE_PATH"], showcase)
    item = {"Title": "Site", "Link": "https://site.dev"}
    resp = client.post("/editor/save", json={
        "item": item, "showcase_only": True, "link": "https://site.dev"
    })
    assert resp.get_json()["success"]
    saved = _read_json(app.config["SHOWCASE_PATH"])
    assert "Skip" not in saved[0]


def test_editor_save_showcase_only_not_found(client, app):
    _write_json(app.config["SHOWCASE_PATH"], [])
    resp = client.post("/editor/save", json={
        "item": {"Title": "X"}, "showcase_only": True, "link": "https://nonexistent.dev"
    })
    assert resp.status_code == 404


def test_editor_save_both_entry_syncs_skip(client, app, sample_bundledb, sample_showcase):
    _write_json(app.config["BUNDLEDB_PATH"], sample_bundledb)
    _write_json(app.config["SHOWCASE_PATH"], sample_showcase)
    edited = sample_bundledb[1].copy()
    edited["Skip"] = True
    edited["screenshotpath"] = "/screenshots/cool11ty-dev.jpg"
    edited["leaderboardLink"] = "https://www.11ty.dev/speedlify/cool11ty-dev/"
    resp = client.post("/editor/save", json={"item": edited, "link": sample_bundledb[1]["Link"]})
    assert resp.get_json()["success"]
    # Skip should be in bundledb
    bundledb = _read_json(app.config["BUNDLEDB_PATH"])
    assert bundledb[1].get("Skip") is True
    # Skip should also be in showcase-data
    showcase = _read_json(app.config["SHOWCASE_PATH"])
    assert showcase[0].get("Skip") is True


# --- POST /editor/delete (showcase-only) ---

def test_editor_delete_showcase_only(client, app):
    showcase = [
        {"title": "Keep", "link": "https://keep.dev"},
        {"title": "Delete Me", "link": "https://delete.dev"},
        {"title": "Also Keep", "link": "https://also.dev"},
    ]
    _write_json(app.config["SHOWCASE_PATH"], showcase)
    resp = client.post("/editor/delete", json={
        "showcase_only": True, "link": "https://delete.dev"
    })
    assert resp.get_json()["success"]
    saved = _read_json(app.config["SHOWCASE_PATH"])
    assert len(saved) == 2
    assert saved[0]["title"] == "Keep"
    assert saved[1]["title"] == "Also Keep"


def test_editor_delete_showcase_only_removes_build_output(client, app, showcase_dir):
    _write_json(app.config["SHOWCASE_PATH"],
                [{"title": "Delete Me", "link": "https://delete.dev"}])
    page = showcase_dir / "delete-dev"
    page.mkdir()

    resp = client.post("/editor/delete", json={
        "showcase_only": True, "link": "https://delete.dev"
    })

    data = resp.get_json()
    assert data["success"]
    assert data["showcase_output"]["status"] == "deleted"
    assert not page.exists()


def test_editor_delete_showcase_only_not_found(client, app):
    _write_json(app.config["SHOWCASE_PATH"], [])
    resp = client.post("/editor/delete", json={
        "showcase_only": True, "link": "https://nonexistent.dev"
    })
    assert resp.status_code == 404


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


# --- POST /create-blog-post/check ---

def test_check_blog_post_exists_true(client):
    from unittest.mock import patch
    with patch("app.blog_post_exists", return_value=True):
        resp = client.post("/create-blog-post/check", json={"issue_number": 100})
    assert resp.get_json()["exists"] is True


def test_check_blog_post_exists_false(client):
    from unittest.mock import patch
    with patch("app.blog_post_exists", return_value=False):
        resp = client.post("/create-blog-post/check", json={"issue_number": 100})
    assert resp.get_json()["exists"] is False


def test_check_blog_post_no_issue(client):
    resp = client.post("/create-blog-post/check", json={})
    assert resp.get_json()["exists"] is False


# --- POST /create-blog-post/summarize ---

def test_summarize_returns_summaries(client):
    from unittest.mock import patch
    with patch("app.summarize_blog_post", return_value="A great summary."):
        resp = client.post("/create-blog-post/summarize", json={
            "posts": [
                {"link": "https://example.com/post1", "title": "Post 1"},
                {"link": "https://example.com/post2", "title": "Post 2"},
            ]
        })
    data = resp.get_json()
    assert "summaries" in data
    assert data["summaries"]["https://example.com/post1"] == "A great summary."
    assert data["summaries"]["https://example.com/post2"] == "A great summary."


def test_summarize_empty_posts(client):
    resp = client.post("/create-blog-post/summarize", json={"posts": []})
    data = resp.get_json()
    assert data["summaries"] == {}


def test_summarize_skips_empty_links(client):
    from unittest.mock import patch
    with patch("app.summarize_blog_post", return_value="Summary.") as mock_sum:
        resp = client.post("/create-blog-post/summarize", json={
            "posts": [{"link": "", "title": "No Link"}, {"link": "https://a.com", "title": "A"}]
        })
    data = resp.get_json()
    assert "" not in data["summaries"]
    assert data["summaries"]["https://a.com"] == "Summary."
    mock_sum.assert_called_once_with("https://a.com")


# --- _commit_and_push_bundledb() ---

def _completed(cmd, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)


def _fake_git(calls, status="", ahead="0", ahead_rc=0, commit_rc=0, push_rc=0):
    """Stand in for subprocess.run, dispatching on the git subcommand."""
    def run(cmd, **kwargs):
        calls.append(cmd[1])
        sub = cmd[1]
        if sub == "status":
            return _completed(cmd, 0, stdout=status)
        if sub == "rev-list":
            return _completed(cmd, ahead_rc, stdout=ahead,
                              stderr="fatal: no upstream configured")
        if sub == "add":
            return _completed(cmd, 0)
        if sub == "commit":
            return _completed(cmd, commit_rc, stderr="nothing to commit")
        if sub == "push":
            return _completed(cmd, push_rc, stderr="rejected: non-fast-forward")
        raise AssertionError(f"unexpected git command: {cmd}")
    return run


def test_commit_and_push_does_nothing_when_clean_and_in_sync(monkeypatch):
    calls = []
    monkeypatch.setattr(app_module.subprocess, "run", _fake_git(calls))

    result = app_module._commit_and_push_bundledb()

    assert result["success"] is True
    assert "push" not in calls
    assert "commit" not in calls


def test_commit_and_push_pushes_unpushed_commits_when_tree_is_clean(monkeypatch):
    """A local commit that never reached origin must still be pushed.

    The early return on a clean tree fired before the push, so a deploy reported
    success while the commit stayed local.
    """
    calls = []
    monkeypatch.setattr(app_module.subprocess, "run", _fake_git(calls, status="", ahead="2"))

    result = app_module._commit_and_push_bundledb()

    assert result["success"] is True
    assert "push" in calls
    assert "commit" not in calls
    assert "2" in result["message"]


def test_commit_and_push_commits_and_pushes_a_dirty_tree(monkeypatch):
    calls = []
    monkeypatch.setattr(app_module.subprocess, "run",
                        _fake_git(calls, status=" M bundledb.json"))

    result = app_module._commit_and_push_bundledb()

    assert result["success"] is True
    assert calls.count("push") == 1
    assert "add" in calls and "commit" in calls


def test_commit_and_push_pushes_once_when_dirty_and_ahead(monkeypatch):
    calls = []
    monkeypatch.setattr(app_module.subprocess, "run",
                        _fake_git(calls, status=" M bundledb.json", ahead="3"))

    result = app_module._commit_and_push_bundledb()

    assert result["success"] is True
    assert calls.count("push") == 1


def test_commit_and_push_reports_push_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(app_module.subprocess, "run",
                        _fake_git(calls, status="", ahead="1", push_rc=1))

    result = app_module._commit_and_push_bundledb()

    assert result["success"] is False
    assert "push failed" in result["message"]


def test_commit_and_push_reports_commit_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(app_module.subprocess, "run",
                        _fake_git(calls, status=" M bundledb.json", commit_rc=1))

    result = app_module._commit_and_push_bundledb()

    assert result["success"] is False
    assert "commit failed" in result["message"]
    assert "push" not in calls


def test_commit_and_push_tolerates_a_branch_with_no_upstream(monkeypatch):
    """rev-list against @{u} fails without an upstream; fall back to old behavior."""
    calls = []
    monkeypatch.setattr(app_module.subprocess, "run",
                        _fake_git(calls, status="", ahead="", ahead_rc=128))

    result = app_module._commit_and_push_bundledb()

    assert result["success"] is True
    assert "push" not in calls
