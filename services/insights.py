"""Generate insights data from bundledb.json and showcase-data.json.

Ported from dbtools/generate-insights.js — produces insightsdata.json and two
CSV files.  HTML/CSS/SVG generation is NOT ported (out of scope).
"""

import json
import os
from datetime import datetime

from services.slugify import slugify

# Month when site jump should appear (11tybundle.dev redesign)
SITE_JUMP_MONTH = "2026-01"


# ---------------------------------------------------------------------------
# Date utilities
# ---------------------------------------------------------------------------

def _parse_date(date_str):
    """Parse a date string, return a datetime or None."""
    if not date_str:
        return None
    # Handle both YYYY-MM-DD and YYYY-MM-DDTHH:mm:ss.000 formats
    s = date_str.replace("Z", "+00:00") if date_str.endswith("Z") else date_str
    try:
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


def _get_year_month(dt):
    """Return 'YYYY-MM' string from a datetime."""
    return f"{dt.year}-{dt.month:02d}"


def _get_all_months_between(start_dt, end_dt):
    """Return list of 'YYYY-MM' strings from start to end (inclusive)."""
    months = []
    year, month = start_dt.year, start_dt.month
    end_year, end_month = end_dt.year, end_dt.month
    while (year, month) <= (end_year, end_month):
        months.append(f"{year}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


# ---------------------------------------------------------------------------
# Metric computations
# ---------------------------------------------------------------------------

def _compute_entry_type_metrics(entries):
    valid_types = ["blog post", "site", "release"]
    filtered = [e for e in entries if not e.get("Skip") and e.get("Type") in valid_types]

    counts = {"blog post": 0, "site": 0, "release": 0}
    for e in filtered:
        counts[e["Type"]] += 1

    dates = [_parse_date(e.get("Date")) for e in filtered]
    dates = [d for d in dates if d is not None]
    if not dates:
        return {"counts": counts, "cumulative": {}, "months": []}

    min_date = min(dates)
    max_date = max(dates)
    all_months = _get_all_months_between(min_date, max_date)

    # Build per-month counts first for efficiency
    month_type_counts = {}
    for e in filtered:
        d = _parse_date(e.get("Date"))
        if d:
            ym = _get_year_month(d)
            key = (ym, e["Type"])
            month_type_counts[key] = month_type_counts.get(key, 0) + 1

    cumulative = {}
    for t in valid_types:
        cumulative[t] = {}
        running = 0
        for month in all_months:
            running += month_type_counts.get((month, t), 0)
            cumulative[t][month] = running

    return {"counts": counts, "cumulative": cumulative, "months": all_months}


def _compute_site_jump(entries, showcase_data):
    bundle_links = set(e.get("Link") for e in entries if not e.get("Skip"))
    return sum(1 for s in showcase_data if not s.get("skip") and s.get("link") not in bundle_links)


def _compute_author_contributions(entries):
    filtered = [e for e in entries if not e.get("Skip") and e.get("Author")]
    author_data = {}

    for e in filtered:
        author = e["Author"]
        if author not in author_data:
            author_data[author] = {"count": 0, "site": e.get("AuthorSite", "")}
        author_data[author]["count"] += 1
        if e.get("AuthorSite") and not author_data[author]["site"]:
            author_data[author]["site"] = e["AuthorSite"]

    ranges = {"1-2": 0, "3-4": 0, "5-10": 0, "11-20": 0, "21+": 0}
    for info in author_data.values():
        c = info["count"]
        if c >= 21:
            ranges["21+"] += 1
        elif c >= 11:
            ranges["11-20"] += 1
        elif c >= 5:
            ranges["5-10"] += 1
        elif c >= 3:
            ranges["3-4"] += 1
        elif c >= 1:
            ranges["1-2"] += 1

    prolific = [
        {"name": name, "site": data["site"], "count": data["count"]}
        for name, data in author_data.items()
        if data["count"] >= 5
    ]
    # JS: .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
    # localeCompare is case-insensitive
    prolific.sort(key=lambda a: (-a["count"], a["name"].casefold()))

    return {"ranges": ranges, "prolificAuthors": prolific}


def _compute_category_metrics(entries):
    filtered = [e for e in entries
                if not e.get("Skip") and e.get("Categories") and len(e["Categories"]) > 0]

    excluded_categories = {"How to..."}
    category_counts = {}
    for e in filtered:
        for cat in e["Categories"]:
            if cat not in excluded_categories:
                category_counts[cat] = category_counts.get(cat, 0) + 1

    # JS Array.sort is stable — ties preserve insertion order (no alphabetical tiebreak)
    sorted_cats = sorted(category_counts.items(), key=lambda x: -x[1])[:20]
    top20 = [{"name": name, "count": count} for name, count in sorted_cats]

    dates = [_parse_date(e.get("Date")) for e in filtered]
    dates = [d for d in dates if d is not None]
    if not dates:
        return {"top20": top20, "cumulative": {}, "months": []}

    min_date = min(dates)
    max_date = max(dates)
    all_months = _get_all_months_between(min_date, max_date)

    # Build per-month-per-category counts for efficiency
    month_cat_counts = {}
    for e in filtered:
        d = _parse_date(e.get("Date"))
        if d:
            ym = _get_year_month(d)
            for cat in e["Categories"]:
                if cat not in excluded_categories:
                    key = (ym, cat)
                    month_cat_counts[key] = month_cat_counts.get(key, 0) + 1

    cumulative = {}
    for item in top20:
        name = item["name"]
        cumulative[name] = {}
        running = 0
        for month in all_months:
            running += month_cat_counts.get((month, name), 0)
            cumulative[name][month] = running

    return {"top20": top20, "cumulative": cumulative, "months": all_months}


def _compute_missing_data_metrics(entries, exclusions=None):
    if exclusions is None:
        exclusions = []

    normalize_url = lambda url: (url or "").rstrip("/")
    exclusion_set = set(
        f"{normalize_url(e.get('url'))}|{e.get('missingDataType')}"
        for e in exclusions
    )
    is_excluded = lambda author_site, data_type: (
        f"{normalize_url(author_site)}|{data_type}" in exclusion_set
    )

    filtered = [e for e in entries if not e.get("Skip")]

    # Get unique authors and their entries
    author_entries = {}
    for e in filtered:
        author = e.get("Author")
        if not author:
            continue
        if author not in author_entries:
            author_entries[author] = {
                "rssLink": e.get("rssLink"),
                "favicon": e.get("favicon"),
                "authorSiteDescription": e.get("AuthorSiteDescription"),
                "authorSite": e.get("AuthorSite"),
            }
        # Update with latest values if present
        if e.get("rssLink"):
            author_entries[author]["rssLink"] = e["rssLink"]
        if e.get("favicon"):
            author_entries[author]["favicon"] = e["favicon"]
        if e.get("AuthorSiteDescription"):
            author_entries[author]["authorSiteDescription"] = e["AuthorSiteDescription"]
        if e.get("AuthorSite"):
            author_entries[author]["authorSite"] = e["AuthorSite"]

    authors_missing_rss = []
    authors_missing_favicon = []
    authors_missing_description = []

    for author_name, author in author_entries.items():
        author_info = {"name": author_name, "site": author.get("authorSite") or ""}

        rss = author.get("rssLink")
        if not rss or (isinstance(rss, str) and rss.strip() == ""):
            if not is_excluded(author.get("authorSite"), "rss feed"):
                authors_missing_rss.append(author_info)

        if author.get("favicon") == "#icon-person-circle":
            if not is_excluded(author.get("authorSite"), "favicon"):
                authors_missing_favicon.append(author_info)

        desc = author.get("authorSiteDescription")
        if not desc or (isinstance(desc, str) and desc.strip() == ""):
            if not is_excluded(author.get("authorSite"), "description"):
                authors_missing_description.append(author_info)

    # JS: .sort((a, b) => a.name.localeCompare(b.name)) — case-insensitive
    authors_missing_rss.sort(key=lambda a: a["name"].casefold())
    authors_missing_favicon.sort(key=lambda a: a["name"].casefold())
    authors_missing_description.sort(key=lambda a: a["name"].casefold())

    # Blog posts missing description
    blog_posts = [e for e in filtered if e.get("Type") == "blog post"]
    posts_missing_desc = []
    for e in blog_posts:
        desc = e.get("description")
        if desc and (not isinstance(desc, str) or desc.strip() != ""):
            continue
        # Build category link matching JS logic
        date_str = e.get("Date", "")
        try:
            date_iso = datetime.fromisoformat(
                date_str.replace("Z", "+00:00") if date_str.endswith("Z") else date_str
            ).strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            date_iso = ""
        cats = e.get("Categories") or []
        category = slugify(cats[0]) if cats else None
        post_id = f"post-{date_iso}-{e.get('slugifiedTitle', '')}-{e.get('slugifiedAuthor', '')}"
        if category:
            category_link = f"/categories/{category}/?bundleitem_highlight=#{post_id}"
        else:
            category_link = e.get("Link", "")
        posts_missing_desc.append({
            "title": e.get("Title", ""),
            "link": category_link,
            "author": e.get("Author", ""),
            "slugifiedAuthor": e.get("slugifiedAuthor", ""),
        })

    # JS: .sort((a, b) => a.author.localeCompare(b.author) || a.title.localeCompare(b.title))
    posts_missing_desc.sort(key=lambda p: (p["author"].casefold(), p["title"].casefold()))

    return {
        "totalAuthors": len(author_entries),
        "missingRssLink": len(authors_missing_rss),
        "missingFavicon": len(authors_missing_favicon),
        "missingAuthorSiteDescription": len(authors_missing_description),
        "totalBlogPosts": len(blog_posts),
        "missingBlogDescription": len(posts_missing_desc),
        "authorsWithMissingRssLink": authors_missing_rss,
        "authorsWithMissingFavicon": authors_missing_favicon,
        "authorsWithMissingDescription": authors_missing_description,
        "postsWithMissingDescription": posts_missing_desc,
    }


def _compute_entries_by_year(entries, site_jump):
    filtered = [e for e in entries
                if not e.get("Skip") and e.get("Type") in ("blog post", "site")]

    year_counts = {}
    for e in filtered:
        d = _parse_date(e.get("Date"))
        if not d:
            continue
        year = d.year
        if year not in year_counts:
            year_counts[year] = {"blogPosts": 0, "sites": 0}
        if e["Type"] == "blog post":
            year_counts[year]["blogPosts"] += 1
        elif e["Type"] == "site":
            year_counts[year]["sites"] += 1

    # Apply site jump to the jump year
    if site_jump and site_jump["amount"] > 0 and site_jump.get("month"):
        jump_year = int(site_jump["month"].split("-")[0])
        if jump_year in year_counts:
            year_counts[jump_year]["sites"] += site_jump["amount"]

    years = sorted(year_counts.keys())
    cumulative_blog = 0
    cumulative_sites = 0
    result = []

    for i, year in enumerate(years):
        prev_blog = cumulative_blog
        prev_sites = cumulative_sites
        cumulative_blog += year_counts[year]["blogPosts"]
        cumulative_sites += year_counts[year]["sites"]

        growth = cumulative_blog - prev_blog if i > 0 else 0
        s_growth = cumulative_sites - prev_sites if i > 0 else 0

        result.append({
            "year": str(year),
            "blogPosts": cumulative_blog,
            "blogPostsGrowth": growth if growth else "\u2014",
            "sites": cumulative_sites if cumulative_sites else "\u2014",
            "sitesGrowth": s_growth if s_growth else "\u2014",
        })

    return result


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------

def _generate_insights_data(metrics, entries, showcase_data):
    entry_types = metrics["entryTypes"]
    author_contributions = metrics["authorContributions"]
    categories = metrics["categories"]
    missing_data = metrics["missingData"]
    site_jump = metrics["siteJump"]
    entries_by_year = metrics["entriesByYear"]

    # generatedDate: local-timezone ISO datetime matching JS behavior
    d = datetime.now()
    generated_date = d.isoformat()

    months = entry_types.get("months", [])

    # Build cumulative growth series
    blog_series = [entry_types["cumulative"].get("blog post", {}).get(m, 0) for m in months]

    site_series = []
    jump_idx = months.index(site_jump["month"]) if site_jump["month"] in months else -1
    for i, m in enumerate(months):
        base = entry_types["cumulative"].get("site", {}).get(m, 0)
        if site_jump["amount"] > 0 and jump_idx >= 0 and i >= jump_idx:
            site_series.append(base + site_jump["amount"])
        else:
            site_series.append(base)

    release_series = [entry_types["cumulative"].get("release", {}).get(m, 0) for m in months]

    cat_months = categories.get("months", [])
    top15 = categories["top20"][:15]

    total_authors = missing_data["totalAuthors"]
    total_blog_posts = missing_data["totalBlogPosts"]

    def pct(num, denom):
        # JS: +(NaN).toFixed(1) → NaN → JSON null when denom is 0
        if not denom:
            return None
        # JS: +((n/d*100).toFixed(1)) — the unary + drops trailing zeros,
        # e.g. 50.0 → 50 (int in JSON).  Match by converting whole floats.
        val = round(num / denom * 100, 1)
        return int(val) if val == int(val) else val

    return {
        "generatedDate": generated_date,
        "stats": {
            "totalEntries": sum(entry_types["counts"].values()) + (site_jump.get("amount") or 0),
            "blogPosts": entry_types["counts"]["blog post"],
            "sites": entry_types["counts"]["site"] + (site_jump.get("amount") or 0),
            "releases": entry_types["counts"]["release"],
            "totalAuthors": total_authors,
            "totalShowcase": len(showcase_data),
            "prolificAuthorCount": len(author_contributions["prolificAuthors"]),
        },
        "entriesByYear": entries_by_year,
        "cumulativeGrowth": {
            "months": months,
            "series": {
                "blogPosts": blog_series,
                "sites": site_series,
                "releases": release_series,
            },
        },
        "siteJump": {
            "month": site_jump["month"],
            "amount": site_jump["amount"],
        },
        "milestones": [
            {"month": "2022-01", "label": "v1.0.0", "type": "minor"},
            {"month": "2023-02", "label": "v2.0.0", "type": "minor"},
            {"month": "2023-05", "label": "11tybundle.dev launch", "type": "major"},
            {"month": "2024-10", "label": "v3.0.0", "type": "minor"},
        ],
        "categoryRanking": top15,
        "categoryGrowth": {
            "months": cat_months,
            "series": {
                c["name"]: [categories["cumulative"].get(c["name"], {}).get(m, 0) for m in cat_months]
                for c in top15
            },
        },
        "authorDistribution": [
            {"range": r, "count": c}
            for r, c in author_contributions["ranges"].items()
        ],
        "prolificAuthors": author_contributions["prolificAuthors"],
        "missingData": {
            "totalAuthors": total_authors,
            "totalBlogPosts": total_blog_posts,
            "rssLink": {
                "count": missing_data["missingRssLink"],
                "percentage": pct(missing_data["missingRssLink"], total_authors),
                "authors": missing_data["authorsWithMissingRssLink"],
            },
            "favicon": {
                "count": missing_data["missingFavicon"],
                "percentage": pct(missing_data["missingFavicon"], total_authors),
                "authors": missing_data["authorsWithMissingFavicon"],
            },
            "authorDescription": {
                "count": missing_data["missingAuthorSiteDescription"],
                "percentage": pct(missing_data["missingAuthorSiteDescription"], total_authors),
                "authors": missing_data["authorsWithMissingDescription"],
            },
            "blogDescription": {
                "count": missing_data["missingBlogDescription"],
                "percentage": pct(missing_data["missingBlogDescription"], total_blog_posts),
                "posts": missing_data["postsWithMissingDescription"],
            },
        },
    }


def _generate_csv(entries_by_year):
    header = "Year,Blog Posts,Sites"
    rows = []
    for row in entries_by_year:
        sites = row["sites"] if isinstance(row["sites"], int) else 0
        rows.append(f"{row['year']},{row['blogPosts']},{sites}")
    return "\n".join([header] + rows)


def _generate_author_csv(entries):
    blog_posts = [e for e in entries if not e.get("Skip") and e.get("Type") == "blog post"]

    authors_by_year = {}
    for entry in blog_posts:
        d = _parse_date(entry.get("Date"))
        if not d or not entry.get("Author"):
            continue
        year = d.year
        if year not in authors_by_year:
            authors_by_year[year] = set()
        authors_by_year[year].add(entry["Author"])

    years = sorted(authors_by_year.keys())
    cumulative_authors = set()
    header = "Year,Authors"
    rows = []
    for year in years:
        cumulative_authors |= authors_by_year[year]
        rows.append(f"{year},{len(cumulative_authors)}")
    return "\n".join([header] + rows)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_insights(
    bundledb_path,
    showcase_path,
    exclusions_path,
    insights_output_path,
    csv_entry_output_path,
    csv_author_output_path,
):
    """Generate insightsdata.json and two CSV files.

    Returns a summary dict with stats counts for logging.
    """
    with open(bundledb_path, "r", encoding="utf-8") as f:
        entries = json.load(f)
    with open(showcase_path, "r", encoding="utf-8") as f:
        showcase_data = json.load(f)

    exclusions = []
    try:
        with open(exclusions_path, "r", encoding="utf-8") as f:
            exclusions = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    entry_types = _compute_entry_type_metrics(entries)
    site_jump_amount = _compute_site_jump(entries, showcase_data)
    site_jump = {"month": SITE_JUMP_MONTH, "amount": site_jump_amount}

    metrics = {
        "entryTypes": entry_types,
        "authorContributions": _compute_author_contributions(entries),
        "categories": _compute_category_metrics(entries),
        "missingData": _compute_missing_data_metrics(entries, exclusions),
        "siteJump": site_jump,
        "entriesByYear": _compute_entries_by_year(entries, site_jump),
    }

    insights_data = _generate_insights_data(metrics, entries, showcase_data)
    csv_content = _generate_csv(metrics["entriesByYear"])
    csv_author_content = _generate_author_csv(entries)

    # Write outputs
    os.makedirs(os.path.dirname(insights_output_path) or ".", exist_ok=True)
    with open(insights_output_path, "w", encoding="utf-8") as f:
        json.dump(insights_data, f, indent=2)

    os.makedirs(os.path.dirname(csv_entry_output_path) or ".", exist_ok=True)
    with open(csv_entry_output_path, "w", encoding="utf-8") as f:
        f.write(csv_content)

    os.makedirs(os.path.dirname(csv_author_output_path) or ".", exist_ok=True)
    with open(csv_author_output_path, "w", encoding="utf-8") as f:
        f.write(csv_author_content)

    return {
        "totalEntries": insights_data["stats"]["totalEntries"],
        "blogPosts": insights_data["stats"]["blogPosts"],
        "sites": insights_data["stats"]["sites"],
        "releases": insights_data["stats"]["releases"],
        "totalAuthors": insights_data["stats"]["totalAuthors"],
    }
