"""Compare Python issue_records output against the JS genissuerecords output.

Writes fixture data to temp files, runs both implementations, and asserts
identical JSON output.
"""

import json
import os
import subprocess
import textwrap

import pytest

from services.issue_records import generate_issue_records


# Inline JS wrapper that accepts input/output paths as CLI args,
# bypassing the hardcoded config in genissuerecords.js.
JS_WRAPPER = textwrap.dedent("""\
    import { promises as fs } from "fs";

    const buildIssueRecords = (bundleRecords) => {
      const countsByIssue = new Map();
      for (const item of bundleRecords) {
        if (item?.Skip) continue;
        const issueNum = Number(item?.Issue);
        if (!Number.isFinite(issueNum) || issueNum < 1) continue;
        if (!countsByIssue.has(issueNum))
          countsByIssue.set(issueNum, { blogPosts: 0, releases: 0, sites: 0 });
        const bucket = countsByIssue.get(issueNum);
        switch (item.Type) {
          case "blog post": bucket.blogPosts += 1; break;
          case "release":   bucket.releases += 1; break;
          case "site":      bucket.sites += 1; break;
        }
      }
      const maxIssue = Math.max(0, ...countsByIssue.keys());
      const issueRecords = [];
      for (let i = 1; i <= maxIssue; i++) {
        const c = countsByIssue.get(i) || { blogPosts: 0, releases: 0, sites: 0 };
        issueRecords.push({ issue: i, blogPosts: c.blogPosts, releases: c.releases, sites: c.sites });
      }
      return issueRecords;
    };

    const [inputPath, outputPath] = process.argv.slice(2);
    const data = JSON.parse(await fs.readFile(inputPath, "utf8"));
    const result = buildIssueRecords(data);
    await fs.writeFile(outputPath, JSON.stringify(result, null, 2), "utf8");
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
def basic_bundledb():
    """Typical data with multiple issues, types, a gap, and a Skip entry."""
    return [
        {"Issue": 1, "Type": "blog post", "Title": "A"},
        {"Issue": 1, "Type": "blog post", "Title": "B"},
        {"Issue": 1, "Type": "site", "Title": "C"},
        {"Issue": 2, "Type": "release", "Title": "D"},
        # Issue 3 is missing — should appear as zeros
        {"Issue": 4, "Type": "blog post", "Title": "E"},
        {"Issue": 4, "Type": "site", "Title": "F"},
        {"Issue": 4, "Type": "site", "Title": "G"},
        {"Issue": 4, "Type": "blog post", "Title": "H", "Skip": True},
    ]


@pytest.fixture
def edge_bundledb():
    """Edge cases: string Issue numbers, non-standard types, invalid entries."""
    return [
        {"Issue": "5", "Type": "blog post", "Title": "A"},
        {"Issue": "5", "Type": "starter", "Title": "B"},  # starter not counted
        {"Issue": "3", "Type": "site", "Title": "C"},
        {"Issue": 0, "Type": "blog post", "Title": "D"},    # issue 0, ignored
        {"Issue": -1, "Type": "blog post", "Title": "E"},   # negative, ignored
        {"Type": "blog post", "Title": "F"},                 # no Issue field
        {"Issue": "abc", "Type": "blog post", "Title": "G"}, # non-numeric
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestIssueRecordsMatchJS:
    """Verify Python output matches JS output for the same inputs."""

    def _compare(self, bundledb_data, tmp_path):
        input_file = tmp_path / "bundledb.json"
        input_file.write_text(json.dumps(bundledb_data))

        # Python
        py_output = tmp_path / "py_issuerecords.json"
        generate_issue_records(str(input_file), str(py_output))

        # JS
        js_output = tmp_path / "js_issuerecords.json"
        _run_js(JS_WRAPPER, tmp_path, [str(input_file), str(js_output)])

        py_result = json.loads(py_output.read_text())
        js_result = json.loads(js_output.read_text())
        assert py_result == js_result

    def test_basic(self, basic_bundledb, tmp_path):
        self._compare(basic_bundledb, tmp_path)

    def test_edge_cases(self, edge_bundledb, tmp_path):
        self._compare(edge_bundledb, tmp_path)

    def test_empty(self, tmp_path):
        self._compare([], tmp_path)

    def test_single_issue(self, tmp_path):
        self._compare([{"Issue": 1, "Type": "blog post", "Title": "Solo"}], tmp_path)

    def test_all_skipped(self, tmp_path):
        data = [
            {"Issue": 1, "Type": "blog post", "Title": "A", "Skip": True},
            {"Issue": 2, "Type": "site", "Title": "B", "Skip": True},
        ]
        self._compare(data, tmp_path)

    def test_production_data(self, tmp_path):
        """Run both against the real bundledb.json for ultimate confidence."""
        prod_path = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/bundledb.json"
        if not os.path.exists(prod_path):
            pytest.skip("Production bundledb.json not available")

        py_output = tmp_path / "py_issuerecords.json"
        generate_issue_records(prod_path, str(py_output))

        js_output = tmp_path / "js_issuerecords.json"
        _run_js(JS_WRAPPER, tmp_path, [prod_path, str(js_output)])

        py_result = json.loads(py_output.read_text())
        js_result = json.loads(js_output.read_text())
        assert py_result == js_result
