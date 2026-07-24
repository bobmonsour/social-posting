import json

import responses

SHOWCASE_PAGE = (
    "<html><head>"
    '<script>window.__VP_HASH_MAP__=JSON.parse('
    '"{\\"en_showcase.md\\":\\"ABCD1234\\"}")</script>'
    "</head><body></body></html>"
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


def _register(chunk_body):
    responses.add(
        responses.GET,
        "https://sveltiacms.app/en/showcase",
        body=SHOWCASE_PAGE,
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
