import json

import responses


def _write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)


def _read_json(path):
    with open(path) as f:
        return json.load(f)


# --- Draft save ---

def test_draft_save(client, app):
    resp = client.post("/post", data={
        "text": "Draft text here",
        "is_draft": "on",
    }, follow_redirects=False)
    assert resp.status_code == 302

    history = _read_json(app.config["HISTORY_FILE"])
    assert len(history) == 1
    entry = history[0]
    assert entry["is_draft"] is True
    assert entry["text"] == "Draft text here"
    assert entry["platforms"] == []
    assert "id" in entry
    assert "timestamp" in entry
    assert isinstance(entry["images"], list)


# --- Draft load (use) ---

def test_draft_load(client, app):
    # Pre-populate a draft
    draft = {
        "id": "test-draft-123",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "text": "My draft",
        "platforms": [],
        "link_url": None,
        "image_count": 0,
        "is_draft": True,
        "images": [],
    }
    _write_json(app.config["HISTORY_FILE"], [draft])

    resp = client.get("/draft/test-draft-123", follow_redirects=False)
    # Should render compose page (200), not redirect
    assert resp.status_code == 200

    # Draft should be removed from history
    history = _read_json(app.config["HISTORY_FILE"])
    assert len(history) == 0


def test_draft_load_not_found(client, app):
    _write_json(app.config["HISTORY_FILE"], [])
    resp = client.get("/draft/nonexistent", follow_redirects=False)
    assert resp.status_code == 302  # redirect to compose


# --- Draft delete ---

def test_draft_delete(client, app):
    draft = {
        "id": "del-draft-1",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "text": "Delete me",
        "platforms": [],
        "is_draft": True,
        "images": [],
    }
    _write_json(app.config["HISTORY_FILE"], [draft])
    resp = client.post("/draft/del-draft-1/delete", follow_redirects=False)
    assert resp.status_code == 302
    history = _read_json(app.config["HISTORY_FILE"])
    assert len(history) == 0


# --- Post delete ---

def test_post_delete(client, app):
    post = {
        "id": "del-post-1",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "text": "Posted text",
        "platforms": [{"name": "mastodon", "post_url": "https://mastodon.social/@u/123"}],
        "is_draft": False,
        "images": [],
    }
    _write_json(app.config["HISTORY_FILE"], [post])
    resp = client.post("/post/del-post-1/delete", follow_redirects=False)
    assert resp.status_code == 302
    history = _read_json(app.config["HISTORY_FILE"])
    assert len(history) == 0


# --- Failed post retry ---

def test_retry_post(client, app):
    failed = {
        "id": "failed-1",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "text": "Failed text",
        "platforms": [],
        "is_draft": False,
        "is_failed": True,
        "images": [],
    }
    _write_json(app.config["HISTORY_FILE"], [failed])
    resp = client.get("/retry/failed-1", follow_redirects=False)
    assert resp.status_code == 200  # renders compose page
    history = _read_json(app.config["HISTORY_FILE"])
    assert len(history) == 0


def test_retry_legacy_failed(client, app):
    """Legacy failed: not is_draft, empty platforms, no is_failed flag."""
    legacy_failed = {
        "id": "legacy-fail-1",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "text": "Legacy failed",
        "platforms": [],
        "is_draft": False,
        "images": [],
    }
    _write_json(app.config["HISTORY_FILE"], [legacy_failed])
    resp = client.get("/retry/legacy-fail-1", follow_redirects=False)
    assert resp.status_code == 200


# --- Link preview ---

@responses.activate
def test_link_preview(client):
    html = '''
    <html><head>
    <meta property="og:title" content="Preview Title">
    <meta property="og:description" content="Preview Desc">
    </head></html>
    '''
    responses.add(responses.GET, "https://example.com", body=html)
    resp = client.post("/link-preview", json={"url": "https://example.com"})
    data = resp.get_json()
    assert data["title"] == "Preview Title"
    assert data["description"] == "Preview Desc"


def test_link_preview_no_url(client):
    resp = client.post("/link-preview", json={"url": ""})
    assert resp.status_code == 400


# --- Social links endpoint ---

@responses.activate
def test_social_links_endpoint(client):
    html = '<html><body><a href="https://mastodon.social/@test" rel="me">M</a></body></html>'
    responses.add(responses.GET, "https://example.com", body=html)
    responses.add(responses.GET, "https://example.com/about/", body="<html></html>")
    responses.add(responses.GET, "https://example.com/en/", body="<html></html>")

    resp = client.post("/social-links", json={"url": "https://example.com/page"})
    data = resp.get_json()
    assert data["mastodon"] == "@test@mastodon.social"


def test_social_links_no_url(client):
    resp = client.post("/social-links", json={"url": ""})
    assert resp.status_code == 400
