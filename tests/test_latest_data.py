"""Compare Python latest_data output against the JS generate-latest-data output.

Writes fixture data to temp files, runs both implementations, and asserts
identical JSON output.
"""

import json
import os
import subprocess
import textwrap

import pytest

from services.latest_data import generate_latest_data

# Inline JS wrapper — extracts the core logic from generate-latest-data.js
# and accepts paths as CLI args instead of using hardcoded paths.
JS_WRAPPER = textwrap.dedent("""\
    import fs from "fs";
    import path from "path";

    function getLatestIssueNumber(entries) {
      let maxIssue = 0;
      for (const entry of entries) {
        if (entry.Issue) {
          const issueNum = parseInt(entry.Issue, 10);
          if (!isNaN(issueNum)) maxIssue = Math.max(maxIssue, issueNum);
        }
      }
      return maxIssue;
    }

    function getEarliestDate(entries) {
      let earliestDate = null;
      for (const entry of entries) {
        if (entry.Date) {
          const entryDate = new Date(entry.Date);
          if (!isNaN(entryDate.getTime())) {
            if (!earliestDate || entryDate < earliestDate) earliestDate = entryDate;
          }
        }
      }
      return earliestDate;
    }

    const [bundledbPath, showcasePath, bundledbOutPath, showcaseOutPath] = process.argv.slice(2);

    const bundleData = JSON.parse(fs.readFileSync(bundledbPath, "utf8"));
    const latestIssue = getLatestIssueNumber(bundleData);

    const latestEntries = bundleData.filter((entry) => {
      const issueNum = parseInt(entry.Issue, 10);
      return !isNaN(issueNum) && issueNum === latestIssue;
    });

    fs.writeFileSync(bundledbOutPath, JSON.stringify(latestEntries, null, 2), "utf8");

    const earliestDate = getEarliestDate(latestEntries);
    const showcaseData = JSON.parse(fs.readFileSync(showcasePath, "utf8"));

    const filteredShowcase = [];
    for (const entry of showcaseData) {
      if (!entry.date) continue;
      const entryDate = new Date(entry.date);
      if (isNaN(entryDate.getTime())) continue;
      if (entryDate >= earliestDate) filteredShowcase.push(entry);
    }

    fs.writeFileSync(showcaseOutPath, JSON.stringify(filteredShowcase, null, 2), "utf8");
""")


def _run_js(wrapper_code, tmp_path, args):
    """Write an inline JS module to tmp_path and run it with Node."""
    script = tmp_path / "wrapper.mjs"
    script.write_text(wrapper_code)
    result = subprocess.run(
        ["node", str(script)] + args,
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, f"JS failed: {result.stderr}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bundledb_data():
    return [
        {"Issue": 10, "Type": "blog post", "Title": "Old post", "Date": "2025-12-01"},
        {"Issue": 10, "Type": "site", "Title": "Old site", "Date": "2025-12-05"},
        {"Issue": 11, "Type": "blog post", "Title": "New post A", "Date": "2026-01-15"},
        {"Issue": 11, "Type": "blog post", "Title": "New post B", "Date": "2026-01-20"},
        {"Issue": 11, "Type": "site", "Title": "New site", "Date": "2026-01-10"},
        {"Issue": 11, "Type": "release", "Title": "New release", "Date": "2026-01-18"},
    ]


@pytest.fixture
def showcase_data():
    return [
        {"title": "Very old site", "date": "2025-11-01", "link": "https://old.dev"},
        {"title": "Old site", "date": "2025-12-05", "link": "https://older.dev"},
        {"title": "New site", "date": "2026-01-10", "link": "https://new.dev"},
        {"title": "Newer site", "date": "2026-01-20", "link": "https://newer.dev"},
        {"title": "No date site", "link": "https://nodate.dev"},
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLatestDataMatchJS:
    """Verify Python output matches JS output for the same inputs."""

    def _compare(self, bundledb, showcase, tmp_path):
        bundle_file = tmp_path / "bundledb.json"
        showcase_file = tmp_path / "showcase-data.json"
        bundle_file.write_text(json.dumps(bundledb))
        showcase_file.write_text(json.dumps(showcase))

        # Python
        py_bundle_out = tmp_path / "py_bundledb_latest.json"
        py_showcase_out = tmp_path / "py_showcase_latest.json"
        generate_latest_data(
            str(bundle_file), str(showcase_file),
            str(py_bundle_out), str(py_showcase_out),
        )

        # JS
        js_bundle_out = tmp_path / "js_bundledb_latest.json"
        js_showcase_out = tmp_path / "js_showcase_latest.json"
        _run_js(JS_WRAPPER, tmp_path, [
            str(bundle_file), str(showcase_file),
            str(js_bundle_out), str(js_showcase_out),
        ])

        py_bundle = json.loads(py_bundle_out.read_text())
        js_bundle = json.loads(js_bundle_out.read_text())
        assert py_bundle == js_bundle, "bundledb-latest-issue output differs"

        py_showcase = json.loads(py_showcase_out.read_text())
        js_showcase = json.loads(js_showcase_out.read_text())
        assert py_showcase == js_showcase, "showcase-data-latest-issue output differs"

    def test_basic(self, bundledb_data, showcase_data, tmp_path):
        self._compare(bundledb_data, showcase_data, tmp_path)

    def test_single_issue(self, tmp_path):
        bundledb = [
            {"Issue": 1, "Type": "blog post", "Title": "Only", "Date": "2026-01-01"},
        ]
        showcase = [
            {"title": "A", "date": "2026-01-01", "link": "https://a.dev"},
            {"title": "B", "date": "2025-12-01", "link": "https://b.dev"},
        ]
        self._compare(bundledb, showcase, tmp_path)

    def test_string_issue_numbers(self, tmp_path):
        bundledb = [
            {"Issue": "5", "Type": "blog post", "Title": "A", "Date": "2026-02-01"},
            {"Issue": "5", "Type": "site", "Title": "B", "Date": "2026-02-10"},
            {"Issue": "3", "Type": "release", "Title": "C", "Date": "2026-01-01"},
        ]
        showcase = [
            {"title": "X", "date": "2026-02-05", "link": "https://x.dev"},
            {"title": "Y", "date": "2026-01-15", "link": "https://y.dev"},
        ]
        self._compare(bundledb, showcase, tmp_path)

    def test_showcase_with_invalid_dates(self, tmp_path):
        bundledb = [
            {"Issue": 1, "Type": "blog post", "Title": "A", "Date": "2026-01-10"},
        ]
        showcase = [
            {"title": "Good", "date": "2026-01-10", "link": "https://good.dev"},
            {"title": "Bad date", "date": "not-a-date", "link": "https://bad.dev"},
            {"title": "No date", "link": "https://nodate.dev"},
            {"title": "Old", "date": "2025-01-01", "link": "https://old.dev"},
        ]
        self._compare(bundledb, showcase, tmp_path)

    def test_production_data(self, tmp_path):
        """Run both against the real data files for ultimate confidence."""
        prod_bundle = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/bundledb.json"
        prod_showcase = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/showcase-data.json"
        if not os.path.exists(prod_bundle) or not os.path.exists(prod_showcase):
            pytest.skip("Production data files not available")

        self._compare(
            json.loads(open(prod_bundle).read()),
            json.loads(open(prod_showcase).read()),
            tmp_path,
        )
