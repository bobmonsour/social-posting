import json
import os


def _write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)


def _read_json(path):
    with open(path) as f:
        return json.load(f)


# --- POST /editor/stash ---

def test_stash_creates_file_and_appends(client, app, tmp_path):
    stash_path = str(tmp_path / "stashed-entries.json")
    app.config["STASH_PATH"] = stash_path

    resp = client.post("/editor/stash", json={
        "title": "My Post",
        "link": "https://example.com/post",
        "type": "blog post"
    })
    data = resp.get_json()
    assert data["success"] is True
    assert data["count"] == 1

    stash = _read_json(stash_path)
    assert len(stash) == 1
    assert stash[0]["title"] == "My Post"
    assert stash[0]["link"] == "https://example.com/post"
    assert stash[0]["type"] == "blog post"


def test_stash_appends_to_existing(client, app, tmp_path):
    stash_path = str(tmp_path / "stashed-entries.json")
    app.config["STASH_PATH"] = stash_path
    _write_json(stash_path, [{"title": "First", "link": "https://a.com", "type": "site"}])

    resp = client.post("/editor/stash", json={
        "title": "Second",
        "link": "https://b.com",
        "type": "release"
    })
    data = resp.get_json()
    assert data["count"] == 2

    stash = _read_json(stash_path)
    assert stash[0]["title"] == "First"
    assert stash[1]["title"] == "Second"


def test_stash_missing_fields(client, app, tmp_path):
    app.config["STASH_PATH"] = str(tmp_path / "stashed-entries.json")

    resp = client.post("/editor/stash", json={"title": "No link"})
    assert resp.status_code == 400
    assert "required" in resp.get_json()["error"].lower()


def test_stash_no_data(client, app, tmp_path):
    app.config["STASH_PATH"] = str(tmp_path / "stashed-entries.json")

    resp = client.post("/editor/stash", content_type="application/json", data="{}")
    assert resp.status_code == 400


# --- GET /editor/stash/next ---

def test_stash_next_returns_first(client, app, tmp_path):
    stash_path = str(tmp_path / "stashed-entries.json")
    app.config["STASH_PATH"] = stash_path
    _write_json(stash_path, [
        {"title": "First", "link": "https://a.com", "type": "blog post"},
        {"title": "Second", "link": "https://b.com", "type": "site"}
    ])

    resp = client.get("/editor/stash/next")
    data = resp.get_json()
    assert data["entry"]["title"] == "First"
    assert data["entry"]["link"] == "https://a.com"
    assert data["count"] == 2


def test_stash_next_empty(client, app, tmp_path):
    stash_path = str(tmp_path / "stashed-entries.json")
    app.config["STASH_PATH"] = stash_path
    _write_json(stash_path, [])

    resp = client.get("/editor/stash/next")
    data = resp.get_json()
    assert data["entry"] is None
    assert data["count"] == 0


def test_stash_next_missing_file(client, app, tmp_path):
    app.config["STASH_PATH"] = str(tmp_path / "nonexistent.json")

    resp = client.get("/editor/stash/next")
    data = resp.get_json()
    assert data["entry"] is None
    assert data["count"] == 0


# --- POST /editor/stash/remove ---

def test_stash_remove_by_link(client, app, tmp_path):
    stash_path = str(tmp_path / "stashed-entries.json")
    app.config["STASH_PATH"] = stash_path
    _write_json(stash_path, [
        {"title": "First", "link": "https://a.com", "type": "blog post"},
        {"title": "Second", "link": "https://b.com", "type": "site"}
    ])

    resp = client.post("/editor/stash/remove", json={"link": "https://a.com"})
    data = resp.get_json()
    assert data["success"] is True
    assert data["count"] == 1

    stash = _read_json(stash_path)
    assert len(stash) == 1
    assert stash[0]["title"] == "Second"


def test_stash_remove_nonexistent_link(client, app, tmp_path):
    stash_path = str(tmp_path / "stashed-entries.json")
    app.config["STASH_PATH"] = stash_path
    _write_json(stash_path, [
        {"title": "First", "link": "https://a.com", "type": "blog post"}
    ])

    resp = client.post("/editor/stash/remove", json={"link": "https://nothere.com"})
    data = resp.get_json()
    assert data["success"] is True
    assert data["count"] == 1


def test_stash_remove_missing_link(client, app, tmp_path):
    app.config["STASH_PATH"] = str(tmp_path / "stashed-entries.json")

    resp = client.post("/editor/stash/remove", json={"link": ""})
    assert resp.status_code == 400


# --- Stash count in editor template ---

def test_editor_page_passes_stash_count(client, app, tmp_path):
    stash_path = str(tmp_path / "stashed-entries.json")
    app.config["STASH_PATH"] = stash_path
    _write_json(stash_path, [
        {"title": "A", "link": "https://a.com", "type": "blog post"},
        {"title": "B", "link": "https://b.com", "type": "site"}
    ])

    resp = client.get("/")
    assert b"window.stashCount = 2" in resp.data


def test_editor_page_stash_count_zero(client, app, tmp_path):
    stash_path = str(tmp_path / "stashed-entries.json")
    app.config["STASH_PATH"] = stash_path
    _write_json(stash_path, [])

    resp = client.get("/")
    assert b"window.stashCount = 0" in resp.data


def test_editor_page_stash_missing_file(client, app, tmp_path):
    app.config["STASH_PATH"] = str(tmp_path / "nonexistent.json")

    resp = client.get("/")
    assert b"window.stashCount = 0" in resp.data
