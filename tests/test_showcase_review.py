import json
import time
from pathlib import Path
from unittest.mock import patch, call

import pytest

from services.showcase_review import (
    _normalize_url,
    generate_report,
    load_allowlist,
    load_progress,
    load_sites,
    run_review,
    run_single_site,
    save_allowlist,
    save_progress,
)

SAMPLE_SHOWCASE = [
    {"title": "Site One", "link": "https://site-one.com", "description": "First site"},
    {"title": "Site Two", "link": "https://site-two.com", "description": "Second site"},
    {"title": "Site Three", "link": "https://site-three.com", "description": "Third site"},
    {"title": "Site Four", "link": "https://site-four.com", "description": "Fourth site"},
    {"title": "Site Five", "link": "https://site-five.com", "description": "Fifth site"},
]


@pytest.fixture
def showcase_file(tmp_path):
    p = tmp_path / "showcase-data.json"
    p.write_text(json.dumps(SAMPLE_SHOWCASE))
    return p


@pytest.fixture
def allowlist_file(tmp_path):
    return tmp_path / "allowlist.json"


@pytest.fixture
def results_file(tmp_path):
    return tmp_path / "results.json"


@pytest.fixture
def report_file(tmp_path):
    return tmp_path / "report.html"


class TestLoadSites:
    def test_loads_sites_from_file(self, showcase_file):
        sites = load_sites(showcase_file)
        assert len(sites) == 5
        assert sites[0]["title"] == "Site One"
        assert sites[0]["link"] == "https://site-one.com"

    def test_skips_entries_without_link(self, tmp_path):
        data = [{"title": "No Link"}, {"title": "Has Link", "link": "https://example.com"}]
        p = tmp_path / "showcase.json"
        p.write_text(json.dumps(data))
        sites = load_sites(p)
        assert len(sites) == 1
        assert sites[0]["title"] == "Has Link"


class TestAllowlist:
    def test_save_load_roundtrip(self, allowlist_file):
        allowlist = {
            "https://example.com": {"cleared": "2026-02-24", "title": "Example"},
        }
        save_allowlist(allowlist, allowlist_file)
        loaded = load_allowlist(allowlist_file)
        assert loaded == allowlist

    def test_load_returns_empty_when_missing(self, tmp_path):
        result = load_allowlist(tmp_path / "nonexistent.json")
        assert result == {}

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "sub" / "dir" / "allowlist.json"
        save_allowlist({"test": {}}, path)
        assert path.exists()


class TestProgress:
    def test_save_load_roundtrip(self, results_file):
        data = {
            "reviewed": {"https://example.com": {"flagged": False}},
            "started": "2026-02-24T10:00:00",
            "last_updated": None,
        }
        save_progress(data, results_file)
        loaded = load_progress(results_file)
        assert "https://example.com" in loaded["reviewed"]
        assert loaded["last_updated"] is not None

    def test_load_returns_fresh_when_missing(self, tmp_path):
        result = load_progress(tmp_path / "nonexistent.json")
        assert result["reviewed"] == {}
        assert result["started"] is not None


class TestRunReview:
    def _mock_review(self, url):
        """Default mock: return clean review."""
        return {"flagged": False, "pages_checked": 1, "pages": [url]}

    def _mock_review_flagged(self, url):
        return {
            "flagged": True,
            "confidence": "high",
            "summary": "Concerning content",
            "pages_checked": 1,
            "pages": [url],
        }

    def _mock_review_error(self, url):
        return {"flagged": False, "error": "Connection timeout"}

    @patch("services.showcase_review.load_sites")
    @patch("services.showcase_review.review_content")
    @patch("services.showcase_review.time")
    def test_skips_allowlisted_sites(self, mock_time, mock_review, mock_load, results_file, allowlist_file):
        mock_load.return_value = SAMPLE_SHOWCASE[:3]
        mock_review.side_effect = self._mock_review

        # Pre-populate allowlist with first site
        save_allowlist(
            {"https://site-one.com": {"cleared": "2026-02-24", "title": "Site One"}},
            allowlist_file,
        )

        with patch("services.showcase_review.load_allowlist", return_value=load_allowlist(allowlist_file)), \
             patch("services.showcase_review.save_allowlist"):
            progress = run_review(delay=0, results_path=results_file)

        # Should have reviewed 2 sites (skipped site-one)
        reviewed_urls = list(progress["reviewed"].keys())
        assert "https://site-one.com" not in reviewed_urls
        assert len(reviewed_urls) == 2

    @patch("services.showcase_review.load_sites")
    @patch("services.showcase_review.review_content")
    @patch("services.showcase_review.time")
    def test_flagged_sites_not_added_to_allowlist(self, mock_time, mock_review, mock_load, results_file, allowlist_file):
        mock_load.return_value = [SAMPLE_SHOWCASE[0]]
        mock_review.side_effect = self._mock_review_flagged

        saved_allowlists = []
        original_save = save_allowlist
        def capture_save(al, path=None):
            saved_allowlists.append(dict(al))
            original_save(al, path)

        with patch("services.showcase_review.load_allowlist", return_value={}), \
             patch("services.showcase_review.save_allowlist", side_effect=capture_save):
            run_review(delay=0, results_path=results_file)

        # Allowlist should NOT have been saved (flagged site)
        assert len(saved_allowlists) == 0

    @patch("services.showcase_review.load_sites")
    @patch("services.showcase_review.review_content")
    @patch("services.showcase_review.time")
    def test_errored_sites_not_added_to_allowlist(self, mock_time, mock_review, mock_load, results_file):
        mock_load.return_value = [SAMPLE_SHOWCASE[0]]
        mock_review.side_effect = self._mock_review_error

        saved_allowlists = []

        with patch("services.showcase_review.load_allowlist", return_value={}), \
             patch("services.showcase_review.save_allowlist", side_effect=lambda al, p=None: saved_allowlists.append(dict(al))):
            run_review(delay=0, results_path=results_file)

        assert len(saved_allowlists) == 0

    @patch("services.showcase_review.load_sites")
    @patch("services.showcase_review.review_content")
    @patch("services.showcase_review.time")
    def test_clean_sites_added_to_allowlist(self, mock_time, mock_review, mock_load, results_file):
        mock_load.return_value = [SAMPLE_SHOWCASE[0]]
        mock_review.side_effect = self._mock_review

        saved_allowlists = []

        with patch("services.showcase_review.load_allowlist", return_value={}), \
             patch("services.showcase_review.save_allowlist", side_effect=lambda al, p=None: saved_allowlists.append(dict(al))):
            run_review(delay=0, results_path=results_file)

        assert len(saved_allowlists) == 1
        assert "https://site-one.com" in saved_allowlists[0]

    @patch("services.showcase_review.load_sites")
    @patch("services.showcase_review.review_content")
    @patch("services.showcase_review.time")
    def test_ignore_allowlist_reviews_all(self, mock_time, mock_review, mock_load, results_file):
        mock_load.return_value = SAMPLE_SHOWCASE[:3]
        mock_review.side_effect = self._mock_review

        with patch("services.showcase_review.load_allowlist") as mock_load_al, \
             patch("services.showcase_review.save_allowlist"):
            progress = run_review(delay=0, results_path=results_file, ignore_allowlist=True)

        # load_allowlist should not be called when ignore_allowlist=True
        # (run_review sets allowlist to {} directly)
        assert len(progress["reviewed"]) == 3

    @patch("services.showcase_review.load_sites")
    @patch("services.showcase_review.review_content")
    @patch("services.showcase_review.time")
    def test_test_mode_limits_to_10(self, mock_time, mock_review, mock_load, results_file):
        # Create 15 sites
        sites = [{"title": f"Site {i}", "link": f"https://site-{i}.com"} for i in range(15)]
        mock_load.return_value = sites
        mock_review.side_effect = self._mock_review

        with patch("services.showcase_review.load_allowlist", return_value={}), \
             patch("services.showcase_review.save_allowlist"):
            progress = run_review(delay=0, results_path=results_file, limit=10, randomize=True)

        assert len(progress["reviewed"]) == 10

    @patch("services.showcase_review.load_sites")
    @patch("services.showcase_review.review_content")
    @patch("services.showcase_review.time")
    def test_randomize_selects_different_sites(self, mock_time, mock_review, mock_load, results_file):
        """With randomize=True, the selected sites should not always be the first N."""
        sites = [{"title": f"Site {i}", "link": f"https://site-{i}.com"} for i in range(50)]
        mock_load.return_value = sites
        mock_review.side_effect = self._mock_review

        # Run multiple times and collect which sites were reviewed
        all_selected = []
        for _ in range(5):
            r_path = results_file.parent / f"results-{len(all_selected)}.json"
            with patch("services.showcase_review.load_allowlist", return_value={}), \
                 patch("services.showcase_review.save_allowlist"):
                progress = run_review(delay=0, results_path=r_path, limit=5, randomize=True)
            all_selected.append(set(progress["reviewed"].keys()))

        # At least two runs should have different site selections
        assert len(set(frozenset(s) for s in all_selected)) > 1

    @patch("services.showcase_review.load_sites")
    @patch("services.showcase_review.review_content")
    @patch("services.showcase_review.time")
    def test_resume_skips_already_reviewed(self, mock_time, mock_review, mock_load, results_file):
        mock_load.return_value = SAMPLE_SHOWCASE[:3]
        mock_review.side_effect = self._mock_review

        # Pre-populate progress with first site
        existing = {
            "reviewed": {
                "https://site-one.com": {"title": "Site One", "flagged": False},
            },
            "started": "2026-02-24T10:00:00",
            "last_updated": None,
        }
        save_progress(existing, results_file)

        with patch("services.showcase_review.load_allowlist", return_value={}), \
             patch("services.showcase_review.save_allowlist"):
            progress = run_review(delay=0, results_path=results_file)

        # Should have site-one (from existing) + two new ones
        assert len(progress["reviewed"]) == 3
        # review_content should only have been called twice (skipped site-one)
        assert mock_review.call_count == 2

    @patch("services.showcase_review.review_content")
    @patch("services.showcase_review.time")
    def test_rate_limit_backoff(self, mock_time, mock_review, results_file):
        """Rate limit errors trigger backoff retries."""
        rate_error = {"flagged": False, "error": "Rate limit exceeded"}
        clean = {"flagged": False, "pages_checked": 1, "pages": ["https://site-one.com"]}
        mock_review.side_effect = [rate_error, clean]

        with patch("services.showcase_review.load_sites", return_value=[SAMPLE_SHOWCASE[0]]), \
             patch("services.showcase_review.load_allowlist", return_value={}), \
             patch("services.showcase_review.save_allowlist"):
            progress = run_review(delay=0, results_path=results_file)

        # Should have retried and gotten clean result
        assert mock_review.call_count == 2
        result = progress["reviewed"]["https://site-one.com"]
        assert not result.get("flagged")
        assert "error" not in result


class TestRunSingleSite:
    @patch("services.showcase_review.review_content")
    def test_prints_clean_result(self, mock_review, capsys):
        mock_review.return_value = {
            "flagged": False,
            "pages_checked": 2,
            "pages": ["https://example.com", "https://example.com/about"],
        }
        result = run_single_site("https://example.com")
        assert result["flagged"] is False
        output = capsys.readouterr().out
        assert "NOT FLAGGED" in output

    @patch("services.showcase_review.review_content")
    def test_prints_flagged_result(self, mock_review, capsys):
        mock_review.return_value = {
            "flagged": True,
            "confidence": "high",
            "summary": "Hate speech found",
            "pages_checked": 3,
            "pages": ["https://example.com"],
        }
        result = run_single_site("https://example.com")
        assert result["flagged"] is True
        output = capsys.readouterr().out
        assert "FLAGGED" in output
        assert "high" in output


class TestGenerateReport:
    def test_generates_html_with_flagged_entries(self, results_file, report_file):
        data = {
            "reviewed": {
                "https://clean.com": {"title": "Clean", "flagged": False},
                "https://flagged.com": {
                    "title": "Flagged Site",
                    "flagged": True,
                    "confidence": "high",
                    "summary": "Concerning content found",
                    "pages_checked": 2,
                    "pages": ["https://flagged.com", "https://flagged.com/about"],
                },
                "https://error.com": {"title": "Error", "flagged": False, "error": "Timeout"},
            },
            "started": "2026-02-24T10:00:00",
            "last_updated": "2026-02-24T11:00:00",
        }
        save_progress(data, results_file)

        generate_report(results_file, report_file)

        html = report_file.read_text()
        assert "Flagged Site" in html
        assert "Concerning content found" in html
        assert "https://flagged.com/about" in html
        # Clean site should not appear
        assert "Clean" not in html
        # Stats
        assert "3" in html  # sites reviewed
        assert "1" in html  # flagged

    def test_generates_empty_report(self, results_file, report_file):
        data = {
            "reviewed": {
                "https://clean.com": {"title": "Clean", "flagged": False},
            },
            "started": "2026-02-24T10:00:00",
            "last_updated": "2026-02-24T11:00:00",
        }
        save_progress(data, results_file)
        generate_report(results_file, report_file)

        html = report_file.read_text()
        assert "No flagged sites found" in html

    def test_sorts_by_confidence(self, results_file, report_file):
        data = {
            "reviewed": {
                "https://low.com": {
                    "title": "Low", "flagged": True, "confidence": "low",
                    "summary": "Minor", "pages_checked": 1, "pages": [],
                },
                "https://high.com": {
                    "title": "High", "flagged": True, "confidence": "high",
                    "summary": "Major", "pages_checked": 1, "pages": [],
                },
                "https://medium.com": {
                    "title": "Medium", "flagged": True, "confidence": "medium",
                    "summary": "Moderate", "pages_checked": 1, "pages": [],
                },
            },
            "started": "2026-02-24T10:00:00",
            "last_updated": "2026-02-24T11:00:00",
        }
        save_progress(data, results_file)
        generate_report(results_file, report_file)

        html = report_file.read_text()
        high_pos = html.index("High")
        medium_pos = html.index("Medium")
        low_pos = html.index("Low")
        assert high_pos < medium_pos < low_pos

    def test_no_results_file(self, tmp_path, capsys):
        generate_report(tmp_path / "nonexistent.json", tmp_path / "report.html")
        output = capsys.readouterr().out
        assert "No results file" in output


class TestNormalizeUrl:
    def test_strips_trailing_slash(self):
        assert _normalize_url("https://example.com/") == "https://example.com"

    def test_lowercases(self):
        assert _normalize_url("https://Example.COM") == "https://example.com"

    def test_strips_whitespace(self):
        assert _normalize_url("  https://example.com  ") == "https://example.com"
