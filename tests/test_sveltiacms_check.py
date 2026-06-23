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

# The chunk that actually holds the site array
SHOWCASE_SITES_CHUNK = (
    "const showcaseData = /* @__PURE__ */ JSON.parse('"
    + json.dumps(
        [
            {"name": "Eleventy Site", "url": "https://elev.example/", "framework": "eleventy",
             "description": "An 11ty site"},
            {"name": "Jekyll Site", "url": "https://jek.example/", "framework": "jekyll",
             "description": "A jekyll site"},
        ]
    )
    + "');export{showcaseData as s};"
)


@responses.activate
def test_sveltiacms_check_follows_sites_chunk(client, app, tmp_path):
    app.config["SVELTIACMS_SITES_PATH"] = str(tmp_path / "sveltiacms-sites.json")

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
        body=SHOWCASE_SITES_CHUNK,
        status=200,
    )

    resp = client.post("/db-mgmt/sveltiacms-check")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    names = [s["name"] for s in data["sites"]]
    assert names == ["Eleventy Site"]
