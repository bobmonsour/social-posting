"""Compare Python insights output against the JS generate-insights output.

Writes fixture data to temp files, runs both implementations, and asserts
identical JSON output (excluding generatedDate which is time-dependent)
and identical CSV output.
"""

import json
import os
import subprocess
import textwrap

import pytest

from services.insights import generate_insights

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Inline JS wrapper — extracts the core metric/output logic from
# generate-insights.js, strips interactive prompts and HTML/CSS generation,
# accepts paths via process.argv.
JS_WRAPPER = textwrap.dedent("""\
    import fs from "fs";
    import slugify from "@sindresorhus/slugify";

    const SITE_JUMP_MONTH = "2026-01";

    function parseDate(dateStr) {
      if (!dateStr) return null;
      const date = new Date(dateStr);
      return isNaN(date.getTime()) ? null : date;
    }

    function getYearMonth(date) {
      return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
    }

    function getAllMonthsBetween(startDate, endDate) {
      const months = [];
      const current = new Date(startDate.getFullYear(), startDate.getMonth(), 1);
      const end = new Date(endDate.getFullYear(), endDate.getMonth(), 1);
      while (current <= end) {
        months.push(getYearMonth(current));
        current.setMonth(current.getMonth() + 1);
      }
      return months;
    }

    function computeEntryTypeMetrics(entries) {
      const validTypes = ["blog post", "site", "release"];
      const filtered = entries.filter(e => !e.Skip && validTypes.includes(e.Type));
      const counts = { "blog post": 0, site: 0, release: 0 };
      filtered.forEach(e => counts[e.Type]++);
      const dates = filtered.map(e => parseDate(e.Date)).filter(Boolean);
      if (dates.length === 0) return { counts, cumulative: {}, months: [] };
      const minDate = new Date(Math.min(...dates));
      const maxDate = new Date(Math.max(...dates));
      const allMonths = getAllMonthsBetween(minDate, maxDate);
      const cumulative = {};
      validTypes.forEach(type => {
        cumulative[type] = {};
        let running = 0;
        allMonths.forEach(month => {
          const monthEntries = filtered.filter(e => {
            const d = parseDate(e.Date);
            return d && getYearMonth(d) === month && e.Type === type;
          });
          running += monthEntries.length;
          cumulative[type][month] = running;
        });
      });
      return { counts, cumulative, months: allMonths };
    }

    function computeSiteJump(entries, showcaseData) {
      const bundleLinks = new Set(entries.filter(e => !e.Skip).map(e => e.Link));
      return showcaseData.filter(s => !s.skip && !bundleLinks.has(s.link)).length;
    }

    function computeAuthorContributions(entries) {
      const filtered = entries.filter(e => !e.Skip && e.Author);
      const authorData = {};
      filtered.forEach(e => {
        if (!authorData[e.Author]) {
          authorData[e.Author] = { count: 0, site: e.AuthorSite || "" };
        }
        authorData[e.Author].count++;
        if (e.AuthorSite && !authorData[e.Author].site) {
          authorData[e.Author].site = e.AuthorSite;
        }
      });
      const ranges = { "1-2": 0, "3-4": 0, "5-10": 0, "11-20": 0, "21+": 0 };
      Object.values(authorData).forEach(({ count }) => {
        if (count >= 21) ranges["21+"]++;
        else if (count >= 11) ranges["11-20"]++;
        else if (count >= 5) ranges["5-10"]++;
        else if (count >= 3) ranges["3-4"]++;
        else if (count >= 1) ranges["1-2"]++;
      });
      const prolificAuthors = Object.entries(authorData)
        .filter(([, data]) => data.count >= 5)
        .map(([name, data]) => ({ name, site: data.site, count: data.count }))
        .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
      return { ranges, prolificAuthors };
    }

    function computeCategoryMetrics(entries) {
      const filtered = entries.filter(e => !e.Skip && e.Categories && e.Categories.length > 0);
      const excludedCategories = ["How to..."];
      const categoryCounts = {};
      filtered.forEach(e => {
        e.Categories.forEach(cat => {
          if (!excludedCategories.includes(cat)) {
            categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;
          }
        });
      });
      const sortedCategories = Object.entries(categoryCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 20);
      const top20 = sortedCategories.map(([name, count]) => ({ name, count }));
      const dates = filtered.map(e => parseDate(e.Date)).filter(Boolean);
      if (dates.length === 0) return { top20, cumulative: {}, months: [] };
      const minDate = new Date(Math.min(...dates));
      const maxDate = new Date(Math.max(...dates));
      const allMonths = getAllMonthsBetween(minDate, maxDate);
      const cumulative = {};
      top20.forEach(({ name }) => {
        cumulative[name] = {};
        let running = 0;
        allMonths.forEach(month => {
          const monthEntries = filtered.filter(e => {
            const d = parseDate(e.Date);
            return d && getYearMonth(d) === month && e.Categories.includes(name);
          });
          running += monthEntries.length;
          cumulative[name][month] = running;
        });
      });
      return { top20, cumulative, months: allMonths };
    }

    function computeMissingDataMetrics(entries, exclusions = []) {
      const normalizeUrl = url => (url || "").replace(/\\/+$/, "");
      const exclusionSet = new Set(
        exclusions.map(e => `${normalizeUrl(e.url)}|${e.missingDataType}`)
      );
      const isExcluded = (authorSite, dataType) =>
        exclusionSet.has(`${normalizeUrl(authorSite)}|${dataType}`);
      const filtered = entries.filter(e => !e.Skip);
      const authorEntries = {};
      filtered.forEach(e => {
        if (e.Author) {
          if (!authorEntries[e.Author]) {
            authorEntries[e.Author] = {
              entries: [],
              rssLink: e.rssLink,
              favicon: e.favicon,
              authorSiteDescription: e.AuthorSiteDescription,
              authorSite: e.AuthorSite,
              author: e.Author,
            };
          }
          authorEntries[e.Author].entries.push(e);
          if (e.rssLink) authorEntries[e.Author].rssLink = e.rssLink;
          if (e.favicon) authorEntries[e.Author].favicon = e.favicon;
          if (e.AuthorSiteDescription)
            authorEntries[e.Author].authorSiteDescription = e.AuthorSiteDescription;
          if (e.AuthorSite) authorEntries[e.Author].authorSite = e.AuthorSite;
        }
      });
      const authorsWithMissingRssLink = [];
      const authorsWithMissingFavicon = [];
      const authorsWithMissingDescription = [];
      Object.entries(authorEntries).forEach(([authorName, author]) => {
        const authorInfo = { name: authorName, site: author.authorSite || "" };
        if (!author.rssLink || author.rssLink.trim() === "") {
          if (!isExcluded(author.authorSite, "rss feed")) {
            authorsWithMissingRssLink.push(authorInfo);
          }
        }
        if (author.favicon === "#icon-person-circle") {
          if (!isExcluded(author.authorSite, "favicon")) {
            authorsWithMissingFavicon.push(authorInfo);
          }
        }
        if (!author.authorSiteDescription || author.authorSiteDescription.trim() === "") {
          if (!isExcluded(author.authorSite, "description")) {
            authorsWithMissingDescription.push(authorInfo);
          }
        }
      });
      authorsWithMissingRssLink.sort((a, b) => a.name.localeCompare(b.name));
      authorsWithMissingFavicon.sort((a, b) => a.name.localeCompare(b.name));
      authorsWithMissingDescription.sort((a, b) => a.name.localeCompare(b.name));
      const blogPosts = filtered.filter(e => e.Type === "blog post");
      const postsWithMissingDescription = blogPosts
        .filter(e => !e.description || e.description.trim() === "")
        .map(e => {
          const date = new Date(e.Date).toISOString().slice(0, 10);
          const category = e.Categories && e.Categories.length > 0
            ? slugify(e.Categories[0])
            : null;
          const postId = `post-${date}-${e.slugifiedTitle}-${e.slugifiedAuthor}`;
          const categoryLink = category
            ? `/categories/${category}/?bundleitem_highlight=#${postId}`
            : e.Link;
          return {
            title: e.Title,
            link: categoryLink,
            author: e.Author,
            slugifiedAuthor: e.slugifiedAuthor,
          };
        })
        .sort((a, b) => a.author.localeCompare(b.author) || a.title.localeCompare(b.title));
      return {
        totalAuthors: Object.keys(authorEntries).length,
        missingRssLink: authorsWithMissingRssLink.length,
        missingFavicon: authorsWithMissingFavicon.length,
        missingAuthorSiteDescription: authorsWithMissingDescription.length,
        totalBlogPosts: blogPosts.length,
        missingBlogDescription: postsWithMissingDescription.length,
        authorsWithMissingRssLink,
        authorsWithMissingFavicon,
        authorsWithMissingDescription,
        postsWithMissingDescription,
      };
    }

    function computeEntriesByYear(entries, siteJump) {
      const filtered = entries.filter(e => !e.Skip && (e.Type === "blog post" || e.Type === "site"));
      const yearCounts = {};
      filtered.forEach(e => {
        const d = parseDate(e.Date);
        if (!d) return;
        const year = d.getFullYear();
        if (!yearCounts[year]) yearCounts[year] = { blogPosts: 0, sites: 0 };
        if (e.Type === "blog post") yearCounts[year].blogPosts++;
        else if (e.Type === "site") yearCounts[year].sites++;
      });
      if (siteJump && siteJump.amount > 0 && siteJump.month) {
        const jumpYear = parseInt(siteJump.month.split("-")[0]);
        if (yearCounts[jumpYear]) {
          yearCounts[jumpYear].sites += siteJump.amount;
        }
      }
      const years = Object.keys(yearCounts).map(Number).sort((a, b) => a - b);
      let cumulativeBlogPosts = 0;
      let cumulativeSites = 0;
      return years.map((year, i) => {
        const prevBlogPosts = cumulativeBlogPosts;
        const prevSites = cumulativeSites;
        cumulativeBlogPosts += yearCounts[year].blogPosts;
        cumulativeSites += yearCounts[year].sites;
        const growth = i > 0 ? cumulativeBlogPosts - prevBlogPosts : 0;
        const sGrowth = i > 0 ? cumulativeSites - prevSites : 0;
        return {
          year: `${year}`,
          blogPosts: cumulativeBlogPosts,
          blogPostsGrowth: growth || "\\u2014",
          sites: cumulativeSites || "\\u2014",
          sitesGrowth: sGrowth || "\\u2014",
        };
      });
    }

    function generateInsightsData(metrics, entries, showcaseData) {
      const { entryTypes, authorContributions, categories, missingData, siteJump, entriesByYear } = metrics;
      return {
        generatedDate: "PLACEHOLDER",
        stats: {
          totalEntries: Object.values(entryTypes.counts).reduce((a, b) => a + b, 0) + (siteJump?.amount || 0),
          blogPosts: entryTypes.counts["blog post"],
          sites: entryTypes.counts["site"] + (siteJump?.amount || 0),
          releases: entryTypes.counts["release"],
          totalAuthors: missingData.totalAuthors,
          totalShowcase: showcaseData.length,
          prolificAuthorCount: authorContributions.prolificAuthors.length,
        },
        entriesByYear,
        cumulativeGrowth: {
          months: entryTypes.months,
          series: {
            blogPosts: entryTypes.months.map(m => entryTypes.cumulative["blog post"]?.[m] || 0),
            sites: entryTypes.months.map((m, i) => {
              const base = entryTypes.cumulative["site"]?.[m] || 0;
              if (siteJump && siteJump.amount > 0) {
                const jumpIdx = entryTypes.months.indexOf(siteJump.month);
                if (jumpIdx >= 0 && i >= jumpIdx) return base + siteJump.amount;
              }
              return base;
            }),
            releases: entryTypes.months.map(m => entryTypes.cumulative["release"]?.[m] || 0),
          },
        },
        siteJump: { month: siteJump.month, amount: siteJump.amount },
        milestones: [
          { month: "2022-01", label: "v1.0.0", type: "minor" },
          { month: "2023-02", label: "v2.0.0", type: "minor" },
          { month: "2023-05", label: "11tybundle.dev launch", type: "major" },
          { month: "2024-10", label: "v3.0.0", type: "minor" },
        ],
        categoryRanking: categories.top20.slice(0, 15),
        categoryGrowth: {
          months: categories.months,
          series: Object.fromEntries(
            categories.top20.slice(0, 15).map(c => [
              c.name,
              categories.months.map(m => categories.cumulative[c.name]?.[m] || 0),
            ])
          ),
        },
        authorDistribution: Object.entries(authorContributions.ranges).map(
          ([range, count]) => ({ range, count })
        ),
        prolificAuthors: authorContributions.prolificAuthors,
        missingData: {
          totalAuthors: missingData.totalAuthors,
          totalBlogPosts: missingData.totalBlogPosts,
          rssLink: {
            count: missingData.missingRssLink,
            percentage: +((missingData.missingRssLink / missingData.totalAuthors) * 100).toFixed(1),
            authors: missingData.authorsWithMissingRssLink,
          },
          favicon: {
            count: missingData.missingFavicon,
            percentage: +((missingData.missingFavicon / missingData.totalAuthors) * 100).toFixed(1),
            authors: missingData.authorsWithMissingFavicon,
          },
          authorDescription: {
            count: missingData.missingAuthorSiteDescription,
            percentage: +((missingData.missingAuthorSiteDescription / missingData.totalAuthors) * 100).toFixed(1),
            authors: missingData.authorsWithMissingDescription,
          },
          blogDescription: {
            count: missingData.missingBlogDescription,
            percentage: +((missingData.missingBlogDescription / missingData.totalBlogPosts) * 100).toFixed(1),
            posts: missingData.postsWithMissingDescription,
          },
        },
      };
    }

    function generateCSV(entriesByYear) {
      const header = "Year,Blog Posts,Sites";
      const rows = entriesByYear.map(row => {
        const sites = typeof row.sites === "number" ? row.sites : 0;
        return `${row.year},${row.blogPosts},${sites}`;
      });
      return [header, ...rows].join("\\n");
    }

    function generateAuthorCSV(entries) {
      const blogPosts = entries.filter(e => !e.Skip && e.Type === "blog post");
      const authorsByYear = {};
      for (const entry of blogPosts) {
        const d = parseDate(entry.Date);
        if (!d || !entry.Author) continue;
        const year = d.getFullYear();
        if (!authorsByYear[year]) authorsByYear[year] = new Set();
        authorsByYear[year].add(entry.Author);
      }
      const years = Object.keys(authorsByYear).map(Number).sort((a, b) => a - b);
      const cumulativeAuthors = new Set();
      const header = "Year,Authors";
      const rows = years.map(year => {
        for (const author of authorsByYear[year]) cumulativeAuthors.add(author);
        return `${year},${cumulativeAuthors.size}`;
      });
      return [header, ...rows].join("\\n");
    }

    // Main
    const [bundledbPath, showcasePath, exclusionsPath, insightsOut, csvEntryOut, csvAuthorOut] = process.argv.slice(2);

    const entries = JSON.parse(fs.readFileSync(bundledbPath, "utf8"));
    const showcaseData = JSON.parse(fs.readFileSync(showcasePath, "utf8"));
    let exclusions = [];
    try { exclusions = JSON.parse(fs.readFileSync(exclusionsPath, "utf8")); } catch {}

    const entryTypes = computeEntryTypeMetrics(entries);
    const siteJumpAmount = computeSiteJump(entries, showcaseData);
    const siteJump = { month: SITE_JUMP_MONTH, amount: siteJumpAmount };

    const metrics = {
      entryTypes,
      authorContributions: computeAuthorContributions(entries),
      categories: computeCategoryMetrics(entries),
      missingData: computeMissingDataMetrics(entries, exclusions),
      siteJump,
      entriesByYear: computeEntriesByYear(entries, siteJump),
    };

    const insightsData = generateInsightsData(metrics, entries, showcaseData);
    fs.writeFileSync(insightsOut, JSON.stringify(insightsData, null, 2));
    fs.writeFileSync(csvEntryOut, generateCSV(metrics.entriesByYear));
    fs.writeFileSync(csvAuthorOut, generateAuthorCSV(entries));
""")


def _run_js(wrapper_code, tmp_path, args):
    """Write an inline JS module in the project dir so ESM imports resolve, then run it."""
    script = os.path.join(_PROJECT_DIR, "_test_wrapper.mjs")
    try:
        with open(script, "w") as f:
            f.write(wrapper_code)
        result = subprocess.run(
            ["node", script] + args,
            capture_output=True, text=True, timeout=30, cwd=_PROJECT_DIR,
        )
        assert result.returncode == 0, f"JS failed: {result.stderr}"
    finally:
        if os.path.exists(script):
            os.unlink(script)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def basic_bundledb():
    """Typical data spanning multiple months, types, authors, categories."""
    return [
        {
            "Issue": 1, "Type": "blog post", "Title": "Intro to 11ty",
            "Date": "2023-06-15T10:00:00.000", "Author": "Alice",
            "AuthorSite": "https://alice.dev", "Categories": ["Getting Started"],
            "description": "A great intro", "rssLink": "https://alice.dev/feed.xml",
            "favicon": "alice.png", "AuthorSiteDescription": "Alice's blog",
            "slugifiedTitle": "intro-to-11ty", "slugifiedAuthor": "alice",
            "Link": "https://alice.dev/intro",
        },
        {
            "Issue": 1, "Type": "blog post", "Title": "Advanced 11ty",
            "Date": "2023-06-20T10:00:00.000", "Author": "Alice",
            "AuthorSite": "https://alice.dev", "Categories": ["Getting Started", "Configuration"],
            "description": "Advanced stuff", "rssLink": "https://alice.dev/feed.xml",
            "favicon": "alice.png", "AuthorSiteDescription": "Alice's blog",
            "slugifiedTitle": "advanced-11ty", "slugifiedAuthor": "alice",
            "Link": "https://alice.dev/advanced",
        },
        {
            "Issue": 1, "Type": "blog post", "Title": "My First Post",
            "Date": "2023-07-01T10:00:00.000", "Author": "Bob",
            "AuthorSite": "https://bob.dev", "Categories": ["Getting Started"],
            "description": "", "rssLink": "", "favicon": "#icon-person-circle",
            "AuthorSiteDescription": "",
            "slugifiedTitle": "my-first-post", "slugifiedAuthor": "bob",
            "Link": "https://bob.dev/first",
        },
        {
            "Issue": 2, "Type": "site", "Title": "Cool Site",
            "Date": "2023-08-10T10:00:00.000",
            "Link": "https://coolsite.dev",
        },
        {
            "Issue": 2, "Type": "release", "Title": "v2.0.0",
            "Date": "2023-08-15T10:00:00.000",
            "Link": "https://github.com/11ty/eleventy/releases/tag/v2.0.0",
        },
        {
            "Issue": 3, "Type": "blog post", "Title": "Skipped Post",
            "Date": "2023-09-01T10:00:00.000", "Author": "Charlie",
            "Skip": True, "Categories": ["How to..."],
            "Link": "https://charlie.dev/skipped",
        },
        {
            "Issue": 3, "Type": "blog post", "Title": "No Desc Post",
            "Date": "2024-01-15T10:00:00.000", "Author": "Diana",
            "AuthorSite": "https://diana.dev", "Categories": ["Configuration"],
            "description": "", "rssLink": "https://diana.dev/rss.xml",
            "favicon": "diana.png", "AuthorSiteDescription": "Diana's blog",
            "slugifiedTitle": "no-desc-post", "slugifiedAuthor": "diana",
            "Link": "https://diana.dev/nodesc",
        },
    ]


@pytest.fixture
def basic_showcase():
    return [
        {"title": "Cool Site", "link": "https://coolsite.dev", "date": "2023-08-10"},
        {"title": "Orphan Site", "link": "https://orphan.dev", "date": "2023-09-01"},
    ]


@pytest.fixture
def basic_exclusions():
    return [
        {"url": "https://bob.dev/", "missingDataType": "rss feed"},
    ]


@pytest.fixture
def slugify_bundledb():
    """Data with special characters in categories to test slugify matching."""
    return [
        {
            "Issue": 1, "Type": "blog post", "Title": "Über Post",
            "Date": "2024-01-10T10:00:00.000", "Author": "Müller",
            "AuthorSite": "https://muller.de", "Categories": ["Internationalization"],
            "description": "", "rssLink": "https://muller.de/feed.xml",
            "favicon": "muller.png", "AuthorSiteDescription": "Müller's blog",
            "slugifiedTitle": "uber-post", "slugifiedAuthor": "muller",
            "Link": "https://muller.de/uber",
        },
        {
            "Issue": 1, "Type": "blog post", "Title": "Café & Code",
            "Date": "2024-01-12T10:00:00.000", "Author": "René",
            "AuthorSite": "https://rene.fr", "Categories": ["Data & APIs"],
            "description": "", "rssLink": "", "favicon": "#icon-person-circle",
            "AuthorSiteDescription": "",
            "slugifiedTitle": "cafe-and-code", "slugifiedAuthor": "rene",
            "Link": "https://rene.fr/cafe",
        },
    ]


@pytest.fixture
def prolific_bundledb():
    """Author with 5+ posts to test prolific author detection."""
    entries = []
    for i in range(6):
        entries.append({
            "Issue": i + 1, "Type": "blog post", "Title": f"Post {i}",
            "Date": f"2023-{(i % 12) + 1:02d}-15T10:00:00.000", "Author": "Prolific Pete",
            "AuthorSite": "https://pete.dev", "Categories": ["Getting Started"],
            "description": "desc", "rssLink": "https://pete.dev/feed.xml",
            "favicon": "pete.png", "AuthorSiteDescription": "Pete's blog",
            "slugifiedTitle": f"post-{i}", "slugifiedAuthor": "prolific-pete",
            "Link": f"https://pete.dev/post-{i}",
        })
    # Add a second author with fewer posts
    entries.append({
        "Issue": 1, "Type": "blog post", "Title": "Solo Post",
        "Date": "2023-03-15T10:00:00.000", "Author": "Solo Sam",
        "AuthorSite": "https://sam.dev", "Categories": ["Configuration"],
        "description": "desc", "rssLink": "", "favicon": "#icon-person-circle",
        "AuthorSiteDescription": "",
        "slugifiedTitle": "solo-post", "slugifiedAuthor": "solo-sam",
        "Link": "https://sam.dev/solo",
    })
    return entries


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_inputs(tmp_path, bundledb, showcase, exclusions=None):
    """Write input files and return paths."""
    bundle_file = tmp_path / "bundledb.json"
    showcase_file = tmp_path / "showcase-data.json"
    exclusions_file = tmp_path / "exclusions.json"
    bundle_file.write_text(json.dumps(bundledb))
    showcase_file.write_text(json.dumps(showcase))
    exclusions_file.write_text(json.dumps(exclusions or []))
    return str(bundle_file), str(showcase_file), str(exclusions_file)


def _compare(bundledb, showcase, exclusions, tmp_path):
    """Run Python and JS, compare all outputs (JSON + CSVs)."""
    bundle_path, showcase_path, exclusions_path = _write_inputs(
        tmp_path, bundledb, showcase, exclusions
    )

    # Python outputs
    py_insights = str(tmp_path / "py_insights.json")
    py_csv_entry = str(tmp_path / "py_entry.csv")
    py_csv_author = str(tmp_path / "py_author.csv")
    generate_insights(
        bundle_path, showcase_path, exclusions_path,
        py_insights, py_csv_entry, py_csv_author,
    )

    # JS outputs
    js_insights = str(tmp_path / "js_insights.json")
    js_csv_entry = str(tmp_path / "js_entry.csv")
    js_csv_author = str(tmp_path / "js_author.csv")
    _run_js(JS_WRAPPER, tmp_path, [
        bundle_path, showcase_path, exclusions_path,
        js_insights, js_csv_entry, js_csv_author,
    ])

    py_data = json.loads(open(py_insights).read())
    js_data = json.loads(open(js_insights).read())

    # Exclude generatedDate (time-dependent) — both use placeholder/now()
    py_data.pop("generatedDate", None)
    js_data.pop("generatedDate", None)

    assert py_data == js_data, f"JSON mismatch:\nPython: {json.dumps(py_data, indent=2)}\nJS: {json.dumps(js_data, indent=2)}"

    py_csv_e = open(py_csv_entry).read()
    js_csv_e = open(js_csv_entry).read()
    assert py_csv_e == js_csv_e, f"Entry CSV mismatch:\nPython:\n{py_csv_e}\nJS:\n{js_csv_e}"

    py_csv_a = open(py_csv_author).read()
    js_csv_a = open(js_csv_author).read()
    assert py_csv_a == js_csv_a, f"Author CSV mismatch:\nPython:\n{py_csv_a}\nJS:\n{js_csv_a}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInsightsMatchJS:
    """Verify Python output matches JS output for the same inputs."""

    def test_basic(self, basic_bundledb, basic_showcase, basic_exclusions, tmp_path):
        _compare(basic_bundledb, basic_showcase, basic_exclusions, tmp_path)

    def test_empty(self, tmp_path):
        _compare([], [], [], tmp_path)

    def test_no_showcase(self, basic_bundledb, tmp_path):
        _compare(basic_bundledb, [], [], tmp_path)

    def test_all_skipped(self, tmp_path):
        data = [
            {"Issue": 1, "Type": "blog post", "Title": "A", "Date": "2023-01-01", "Skip": True},
            {"Issue": 2, "Type": "site", "Title": "B", "Date": "2023-02-01", "Skip": True},
        ]
        _compare(data, [], [], tmp_path)

    def test_slugify_categories(self, slugify_bundledb, tmp_path):
        """Categories with special characters should produce identical slugs."""
        _compare(slugify_bundledb, [], [], tmp_path)

    def test_prolific_authors(self, prolific_bundledb, tmp_path):
        _compare(prolific_bundledb, [], [], tmp_path)

    def test_site_jump(self, basic_bundledb, tmp_path):
        """Showcase entries not in bundledb should create a site jump."""
        showcase = [
            {"title": "In DB", "link": "https://alice.dev/intro", "date": "2023-06-15"},
            {"title": "Orphan 1", "link": "https://orphan1.dev", "date": "2023-07-01"},
            {"title": "Orphan 2", "link": "https://orphan2.dev", "date": "2023-08-01"},
        ]
        _compare(basic_bundledb, showcase, [], tmp_path)

    def test_exclusions(self, tmp_path):
        """Exclusions should filter out specific missing data entries."""
        bundledb = [
            {
                "Issue": 1, "Type": "blog post", "Title": "Post",
                "Date": "2023-01-15T10:00:00.000", "Author": "Excluded",
                "AuthorSite": "https://excluded.dev", "Categories": ["General"],
                "description": "desc", "rssLink": "", "favicon": "#icon-person-circle",
                "AuthorSiteDescription": "",
                "slugifiedTitle": "post", "slugifiedAuthor": "excluded",
                "Link": "https://excluded.dev/post",
            },
            {
                "Issue": 1, "Type": "blog post", "Title": "Post 2",
                "Date": "2023-01-20T10:00:00.000", "Author": "NotExcluded",
                "AuthorSite": "https://notexcluded.dev", "Categories": ["General"],
                "description": "desc", "rssLink": "", "favicon": "#icon-person-circle",
                "AuthorSiteDescription": "",
                "slugifiedTitle": "post-2", "slugifiedAuthor": "not-excluded",
                "Link": "https://notexcluded.dev/post2",
            },
        ]
        exclusions = [
            {"url": "https://excluded.dev", "missingDataType": "rss feed"},
            {"url": "https://excluded.dev", "missingDataType": "favicon"},
        ]
        _compare(bundledb, [], exclusions, tmp_path)

    def test_production_data(self, tmp_path):
        """Run both against the real data files for ultimate confidence."""
        prod_bundle = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/bundledb.json"
        prod_showcase = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/showcase-data.json"
        prod_exclusions = os.path.join(_PROJECT_DIR, "data", "insights-exclusions.json")
        if not os.path.exists(prod_bundle) or not os.path.exists(prod_showcase):
            pytest.skip("Production data files not available")

        bundledb = json.loads(open(prod_bundle).read())
        showcase = json.loads(open(prod_showcase).read())
        exclusions = []
        if os.path.exists(prod_exclusions):
            exclusions = json.loads(open(prod_exclusions).read())

        _compare(bundledb, showcase, exclusions, tmp_path)


class TestSlugifyMatchesJS:
    """Verify Python slugify matches @sindresorhus/slugify via JS."""

    JS_SLUGIFY = textwrap.dedent("""\
        import slugify from "@sindresorhus/slugify";
        import fs from "fs";
        const [inputPath, outputPath] = process.argv.slice(2);
        const inputs = JSON.parse(fs.readFileSync(inputPath, "utf8"));
        const results = inputs.map(s => slugify(s));
        fs.writeFileSync(outputPath, JSON.stringify(results, null, 2));
    """)

    def test_slugify_matches(self, tmp_path):
        from services.slugify import slugify

        test_strings = [
            "Getting Started",
            "How to...",
            "Data & APIs",
            "Internationalization",
            "café au lait",
            "über cool",
            "CamelCaseText",
            "it's a test",
            "hello—world",
            "Müller's Ökonomie",
            "  leading  spaces  ",
            "",
            "æther",
            "naïve résumé",
        ]

        input_file = tmp_path / "slugify_input.json"
        input_file.write_text(json.dumps(test_strings))

        py_results = [slugify(s) for s in test_strings]

        js_output = tmp_path / "slugify_output.json"
        _run_js(self.JS_SLUGIFY, tmp_path, [str(input_file), str(js_output)])

        js_results = json.loads(js_output.read_text())
        for i, (py, js) in enumerate(zip(py_results, js_results)):
            assert py == js, f"Slugify mismatch for {test_strings[i]!r}: Python={py!r}, JS={js!r}"
