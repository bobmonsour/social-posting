import json

import responses

SHOWCASE_PAGE = (
    "<html><head>"
    '<script>window.__VP_HASH_MAP__=JSON.parse('
    '"{\\"en_showcase.md\\":\\"ABCD1234\\"}")</script>'
    "</head><body></body></html>"
)

# VitePress v2 (2.0.0-alpha.19+): the hash map is no longer inlined. The page
# preloads the lean.js directly and ships the hash map in a metadata chunk.
SHOWCASE_PAGE_V2 = (
    "<html><head>"
    '<script type="module" src="/assets/chunks/metadata.6779fd66.js"></script>'
    '<link rel="modulepreload" href="/assets/chunks/showcase-sites.CS1rCjQi.js">'
    '<link rel="modulepreload" href="/assets/en_showcase.md.ABCD1234.lean.js">'
    "</head><body></body></html>"
)

# Same VitePress v2 build, but without the lean.js modulepreload hint -- the
# hash map has to be read from the external metadata chunk.
SHOWCASE_PAGE_V2_NO_PRELOAD = (
    "<html><head>"
    '<script type="module" src="/assets/chunks/metadata.6779fd66.js"></script>'
    "</head><body></body></html>"
)

METADATA_CHUNK = (
    'window.__VP_HASH_MAP__=JSON.parse("{\\"en_docs_api.md\\":\\"HVJqFQ4I\\",'
    '\\"en_showcase.md\\":\\"ABCD1234\\"}");'
)

# Modern lean.js: page metadata only, sites imported from a separate chunk
LEAN_JS = (
    'import { d as defineComponent } from "./chunks/framework.xxx.js";'
    'import { s as sites } from "./chunks/showcase-sites.CS1rCjQi.js";'
    "const __pageData = JSON.parse('"
    '{"title":"Sveltia CMS Showcase","frontmatter":{"labels":{}}}'
    "');"
)

SITES = [
    {"name": "Eleventy Site", "url": "https://elev.example/", "framework": "eleventy",
     "description": "An 11ty site"},
    {"name": "Jekyll Site", "url": "https://jek.example/", "framework": "jekyll",
     "description": "A jekyll site"},
]

# Older chunk format: the array lives in a single-quoted JS string literal
SHOWCASE_SITES_CHUNK_SINGLE_QUOTED = (
    "const showcaseData = /* @__PURE__ */ JSON.parse('"
    + json.dumps(SITES)
    + "');export{showcaseData as s};"
)

# Current chunk format: a double-quoted JS string literal with escaped inner quotes
SHOWCASE_SITES_CHUNK_DOUBLE_QUOTED = (
    "var sites = /* @__PURE__ */ JSON.parse("
    + json.dumps(json.dumps(SITES))
    + ");export{sites as t};"
)


def _register(chunk_body, page=SHOWCASE_PAGE, metadata=None):
    responses.add(
        responses.GET,
        "https://sveltiacms.app/en/showcase",
        body=page,
        status=200,
    )
    if metadata is not None:
        responses.add(
            responses.GET,
            "https://sveltiacms.app/assets/chunks/metadata.6779fd66.js",
            body=metadata,
            status=200,
        )
    responses.add(
        responses.GET,
        "https://sveltiacms.app/assets/en_showcase.md.ABCD1234.lean.js",
        body=LEAN_JS,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://sveltiacms.app/assets/chunks/showcase-sites.CS1rCjQi.js",
        body=chunk_body,
        status=200,
    )


@responses.activate
def test_sveltiacms_check_follows_sites_chunk(client, app, tmp_path):
    app.config["SVELTIACMS_SITES_PATH"] = str(tmp_path / "sveltiacms-sites.json")
    _register(SHOWCASE_SITES_CHUNK_SINGLE_QUOTED)

    resp = client.post("/db-mgmt/sveltiacms-check")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    names = [s["name"] for s in data["sites"]]
    assert names == ["Eleventy Site"]


@responses.activate
def test_sveltiacms_check_handles_double_quoted_chunk(client, app, tmp_path):
    """SveltiaCMS now emits JSON.parse("...") with escaped inner quotes."""
    app.config["SVELTIACMS_SITES_PATH"] = str(tmp_path / "sveltiacms-sites.json")
    _register(SHOWCASE_SITES_CHUNK_DOUBLE_QUOTED)

    resp = client.post("/db-mgmt/sveltiacms-check")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    names = [s["name"] for s in data["sites"]]
    assert names == ["Eleventy Site"]


@responses.activate
def test_sveltiacms_check_vitepress_v2_preloaded_lean(client, app, tmp_path):
    """VitePress v2 dropped the inline hash map; the page preloads lean.js."""
    app.config["SVELTIACMS_SITES_PATH"] = str(tmp_path / "sveltiacms-sites.json")
    _register(SHOWCASE_SITES_CHUNK_DOUBLE_QUOTED, page=SHOWCASE_PAGE_V2)

    resp = client.post("/db-mgmt/sveltiacms-check")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    names = [s["name"] for s in data["sites"]]
    assert names == ["Eleventy Site"]


@responses.activate
def test_sveltiacms_check_reads_hash_map_from_metadata_chunk(client, app, tmp_path):
    """With no lean.js preload hint, fall back to the external metadata chunk."""
    app.config["SVELTIACMS_SITES_PATH"] = str(tmp_path / "sveltiacms-sites.json")
    _register(
        SHOWCASE_SITES_CHUNK_DOUBLE_QUOTED,
        page=SHOWCASE_PAGE_V2_NO_PRELOAD,
        metadata=METADATA_CHUNK,
    )

    resp = client.post("/db-mgmt/sveltiacms-check")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    names = [s["name"] for s in data["sites"]]
    assert names == ["Eleventy Site"]


@responses.activate
def test_sveltiacms_check_filters_sites_already_in_bundledb(client, app, tmp_path):
    """A site in bundledb.json but not showcase-data.json is not proposed as new."""
    app.config["SVELTIACMS_SITES_PATH"] = str(tmp_path / "sveltiacms-sites.json")
    with open(app.config["BUNDLEDB_PATH"], "w") as f:
        json.dump([{"Type": "site", "Title": "Eleventy Site",
                    "Link": "http://www.elev.example"}], f)
    with open(app.config["SHOWCASE_PATH"], "w") as f:
        json.dump([], f)
    _register(SHOWCASE_SITES_CHUNK_DOUBLE_QUOTED)

    resp = client.post("/db-mgmt/sveltiacms-check")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()["sites"] == []


@responses.activate
def test_sveltiacms_check_skips_queued_sites_already_in_db(client, app, tmp_path):
    """Queued sites that have since landed in either DB are marked skip."""
    queue_path = tmp_path / "sveltiacms-sites.json"
    app.config["SVELTIACMS_SITES_PATH"] = str(queue_path)
    queue_path.write_text(json.dumps([
        {"name": "In Bundledb", "url": "https://www.in-bundledb.example/"},
        {"name": "In Showcase", "url": "https://in-showcase.example"},
        {"name": "Still New", "url": "https://still-new.example/"},
    ]))
    with open(app.config["BUNDLEDB_PATH"], "w") as f:
        json.dump([{"Type": "site", "Link": "https://in-bundledb.example/"}], f)
    with open(app.config["SHOWCASE_PATH"], "w") as f:
        json.dump([{"link": "http://in-showcase.example/"}], f)
    _register(SHOWCASE_SITES_CHUNK_DOUBLE_QUOTED)

    resp = client.post("/db-mgmt/sveltiacms-check")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data["stale_skipped"] == 2
    assert data["queue_remaining"] == 1

    queue = json.loads(queue_path.read_text())
    skips = {e["name"]: bool(e.get("skip")) for e in queue}
    assert skips == {"In Bundledb": True, "In Showcase": True, "Still New": False}
