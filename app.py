import json
import os
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone

from flask import Flask, redirect, render_template, request, jsonify, url_for, send_from_directory

import config
from modes import all_modes, get_mode
from platforms import get_platform
from platforms.base import LinkCard, MediaAttachment
from services.media import process_uploads, cleanup_uploads, compress_for_bluesky, get_mime_type
from services.link_card import fetch_og_metadata
from services.social_links import extract_social_links
from services.bwe_list import get_bwe_lists, mark_bwe_posted, update_bwe_after_post, delete_bwe_posted, delete_bwe_to_post, add_bwe_to_post
from services.issue_counts import get_latest_issue_counts
from services.insights import generate_insights
from services.issue_records import generate_issue_records
from services.latest_data import generate_latest_data
from services.blog_post import create_blog_post, blog_post_exists, delete_blog_post, edit_blog_post

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB upload limit


@app.template_filter("friendly_time")
def friendly_time(iso_timestamp):
    """Convert ISO timestamp to 'Feb 14, 2026 15:43' format."""
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        return dt.strftime("%b %-d, %Y %H:%M")
    except (ValueError, TypeError):
        return iso_timestamp[:16].replace("T", " ") if iso_timestamp else ""


@app.context_processor
def cache_busting():
    """Provide CSS/JS cache-busting timestamps to templates."""
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    versions = {}
    for key, rel_path in [("css_version", "css/style.css"), ("js_version", "js/editor.js"), ("dbmgmt_js_version", "js/db_mgmt.js")]:
        try:
            versions[key] = int(os.path.getmtime(os.path.join(static_dir, rel_path)))
        except OSError:
            versions[key] = 0
    return versions

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(_BASE_DIR, "posts", "history.json")
DRAFT_IMAGES_DIR = os.path.join(_BASE_DIR, "posts", "draft_images")

BUNDLEDB_PATH = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/bundledb.json"
BUNDLEDB_BACKUP_DIR = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/bundledb-backups"
SHOWCASE_BACKUP_DIR = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/showcase-data-backups"
SHOWCASE_PATH = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb/showcase-data.json"
DBTOOLS_DIR = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/dbtools"
BUNDLEDB_DIR = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundledb"
SCREENSHOT_DIR = os.path.join(BUNDLEDB_DIR, "screenshots")
SCREENSHOT_SCRIPT = os.path.join(_BASE_DIR, "scripts", "capture-screenshot.js")


def _get_path(key):
    """Get a path from app.config, falling back to the module-level constant."""
    defaults = {
        "HISTORY_FILE": HISTORY_FILE,
        "DRAFT_IMAGES_DIR": DRAFT_IMAGES_DIR,
        "BUNDLEDB_PATH": BUNDLEDB_PATH,
        "BUNDLEDB_BACKUP_DIR": BUNDLEDB_BACKUP_DIR,
        "SHOWCASE_BACKUP_DIR": SHOWCASE_BACKUP_DIR,
        "SHOWCASE_PATH": SHOWCASE_PATH,
        "BUNDLEDB_DIR": BUNDLEDB_DIR,
    }
    return app.config.get(key, defaults.get(key, ""))


def _create_backup_with_pruning(source_path, backup_dir, prefix, max_backups=25):
    """Create a timestamped backup and prune old backups beyond max_backups."""
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d--%H%M%S")
    backup_path = os.path.join(backup_dir, f"{prefix}-{timestamp}.json")
    shutil.copy2(source_path, backup_path)

    # Prune oldest backups if over limit
    backups = sorted(f for f in os.listdir(backup_dir) if f.startswith(prefix) and f.endswith(".json"))
    while len(backups) > max_backups:
        os.remove(os.path.join(backup_dir, backups.pop(0)))


def _read_history():
    path = _get_path("HISTORY_FILE")
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return json.load(f)


def _write_history(entries):
    path = _get_path("HISTORY_FILE")
    with open(path, "w") as f:
        json.dump(entries, f, indent=2)


def save_post(text, platforms, link_url=None, image_count=0, is_draft=False, images=None,
              mode=None, platform_texts=None):
    """Prepend a new entry to history and write back."""
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "text": text,
        "platforms": platforms,  # list of {name, post_url}
        "link_url": link_url or None,
        "image_count": image_count,
        "is_draft": is_draft,
        "images": images or [],
    }
    if mode:
        entry["mode"] = mode
        entry["platform_texts"] = platform_texts
    history = _read_history()
    history.insert(0, entry)
    _write_history(history)
    return entry


def load_recent_posts(n=10):
    return _read_history()[:n]


def _annotate_bwe_with_drafts(bwe_to_post, history):
    """Tag each BWE site with its draft_id if a matching draft exists in history."""
    for site in bwe_to_post:
        site["draft_id"] = None
        for entry in history:
            if (entry.get("is_draft") and entry.get("mode") == "11ty-bwe"
                    and entry.get("link_url") == site["url"]):
                site["draft_id"] = entry["id"]
                break


@app.route("/")
def compose():
    bwe_to_post, bwe_posted = get_bwe_lists()
    recent = load_recent_posts()
    _annotate_bwe_with_drafts(bwe_to_post, recent)
    issue_counts = get_latest_issue_counts()
    post_exists = blog_post_exists(issue_counts["issue_number"]) if issue_counts else False
    return render_template(
        "compose.html",
        mastodon_available=config.mastodon_configured(),
        bluesky_available=config.bluesky_configured(),
        discord_available=config.discord_configured(),
        recent_posts=recent,
        modes=all_modes(),
        bwe_to_post=bwe_to_post,
        bwe_posted=bwe_posted,
        issue_counts=issue_counts,
        blog_post_exists=post_exists,
    )


@app.route("/post", methods=["POST"])
def post():
    text = request.form.get("text", "").strip()
    is_draft = request.form.get("is_draft") == "on"
    platforms_selected = request.form.getlist("platforms")
    link_url = request.form.get("link_url", "").strip()

    # Mode support: read per-platform texts if a mode is active
    mode = request.form.get("mode", "").strip() or None
    platform_texts = None
    if mode and get_mode(mode):
        platform_texts = {}
        for pname in ["mastodon", "bluesky", "discord"]:
            pt = request.form.get(f"text_{pname}", "").strip()
            if pt:
                platform_texts[pname] = pt

    if not text and not (mode and platform_texts):
        return render_template(
            "result.html",
            results=[{"platform": "error", "success": False, "error": "No text provided"}],
        )

    draft_images_dir = _get_path("DRAFT_IMAGES_DIR")

    # --- Draft path: save and redirect, skip posting ---
    if is_draft:
        # Process any newly uploaded images
        files = request.files.getlist("images")
        alt_texts = [request.form.get(f"alt_text_{i}", "") for i in range(4)]
        attachments = process_uploads(files, alt_texts)

        # Generate draft ID and save images to persistent storage
        draft_id = str(uuid.uuid4())
        draft_images = []
        draft_dir = os.path.join(draft_images_dir, draft_id)

        # Carry over any existing draft images
        old_draft_id = None
        draft_image_data = request.form.get("draft_image_data", "").strip()
        if draft_image_data:
            try:
                draft_items = json.loads(draft_image_data)
                for item in draft_items:
                    if len(draft_images) + len(attachments) >= config.MAX_IMAGES:
                        break
                    old_did = item["draft_id"]
                    old_draft_id = old_did
                    fname = item["filename"]
                    src = os.path.join(draft_images_dir, old_did, fname)
                    if os.path.exists(src):
                        os.makedirs(draft_dir, exist_ok=True)
                        dest = os.path.join(draft_dir, fname)
                        shutil.copy2(src, dest)
                        draft_images.append({
                            "filename": fname,
                            "alt_text": item.get("alt_text", ""),
                            "mime_type": item.get("mime_type", get_mime_type(src)),
                        })
            except (json.JSONDecodeError, KeyError):
                pass

        # Save newly uploaded images
        if attachments:
            os.makedirs(draft_dir, exist_ok=True)
            for att in attachments:
                filename = os.path.basename(att.file_path)
                dest = os.path.join(draft_dir, filename)
                shutil.copy2(att.file_path, dest)
                draft_images.append({
                    "filename": filename,
                    "alt_text": att.alt_text,
                    "mime_type": att.mime_type,
                })
            cleanup_uploads(attachments)

        # Clean up old draft images directory
        if old_draft_id:
            old_dir = os.path.join(draft_images_dir, old_draft_id)
            shutil.rmtree(old_dir, ignore_errors=True)

        bwe_name = request.form.get("bwe_site_name", "").strip()
        bwe_url = request.form.get("bwe_site_url", "").strip()

        entry = {
            "id": draft_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "text": text,
            "platforms": [],
            "link_url": link_url or None,
            "image_count": len(draft_images),
            "is_draft": True,
            "images": draft_images,
        }
        if mode:
            entry["mode"] = mode
            entry["platform_texts"] = platform_texts
        if bwe_name and bwe_url:
            entry["bwe_site_name"] = bwe_name
            entry["bwe_site_url"] = bwe_url

        history = _read_history()

        # Remove any existing BWE draft with the same URL
        if mode == "11ty-bwe" and link_url:
            for old in history:
                if (old.get("is_draft") and old.get("mode") == "11ty-bwe"
                        and old.get("link_url") == link_url):
                    img_dir = os.path.join(draft_images_dir, old["id"])
                    shutil.rmtree(img_dir, ignore_errors=True)
            history = [e for e in history
                       if not (e.get("is_draft") and e.get("mode") == "11ty-bwe"
                               and e.get("link_url") == link_url)]

        history.insert(0, entry)
        _write_history(history)
        return redirect(url_for("compose"))

    # --- Normal post path ---
    if not platforms_selected:
        return render_template(
            "result.html",
            results=[{"platform": "error", "success": False, "error": "No platform selected"}],
        )

    # Process image uploads (newly selected files)
    files = request.files.getlist("images")
    alt_texts = []
    for i in range(4):
        alt_texts.append(request.form.get(f"alt_text_{i}", ""))
    attachments = process_uploads(files, alt_texts)

    # Process draft images carried over from a saved draft
    draft_image_data = request.form.get("draft_image_data", "").strip()
    draft_id_to_clean = None
    if draft_image_data:
        try:
            draft_items = json.loads(draft_image_data)
            for item in draft_items:
                if len(attachments) >= config.MAX_IMAGES:
                    break
                did = item["draft_id"]
                fname = item["filename"]
                alt = item.get("alt_text", "")
                fpath = os.path.join(draft_images_dir, did, fname)
                if os.path.exists(fpath):
                    mime = get_mime_type(fpath)
                    attachments.append(MediaAttachment(
                        file_path=fpath,
                        mime_type=mime,
                        alt_text=alt,
                    ))
                    draft_id_to_clean = did
        except (json.JSONDecodeError, KeyError):
            pass

    # Process link card
    link_card = None
    if link_url and not attachments:
        link_card = fetch_og_metadata(link_url)

    results = []
    for platform_name in platforms_selected:
        try:
            client = get_platform(platform_name)
            if not client.validate_credentials():
                results.append({
                    "platform": platform_name,
                    "success": False,
                    "error": f"{platform_name} credentials not configured",
                })
                continue

            # Platform-specific content warning
            cw = None
            if platform_name == "mastodon":
                cw = request.form.get("cw_mastodon", "").strip() or None
            elif platform_name == "bluesky":
                cw = request.form.get("cw_bluesky", "").strip() or None
            elif platform_name == "discord":
                cw = request.form.get("cw_discord", "").strip() or None

            # For Bluesky, compress images if needed
            media = attachments
            if platform_name == "bluesky" and attachments:
                for att in attachments:
                    compressed_path = compress_for_bluesky(att.file_path, att.mime_type)
                    if compressed_path != att.file_path:
                        att.file_path = compressed_path

            # Use per-platform text when mode is active
            post_text = (platform_texts or {}).get(platform_name, text)
            if platform_name == "mastodon" and link_card and link_card.url:
                if link_card.url not in post_text:
                    post_text = f"{post_text}\n\n{link_card.url}"

            result = client.post(
                text=post_text,
                media=media if media else None,
                content_warning=cw,
                link_card=link_card if platform_name != "mastodon" else None,
            )
            results.append({
                "platform": result.platform,
                "success": result.success,
                "post_url": result.post_url,
                "error": result.error,
            })
        except Exception as e:
            results.append({
                "platform": platform_name,
                "success": False,
                "error": str(e),
            })

    # Determine success/failure
    any_failed = any(not r["success"] for r in results)
    platform_entries = []
    for r in results:
        if r["success"]:
            platform_entries.append({"name": r["platform"], "post_url": r.get("post_url", "")})

    if any_failed and attachments:
        # Persist images for retry (same as draft image flow)
        failed_id = str(uuid.uuid4())
        failed_dir = os.path.join(draft_images_dir, failed_id)
        failed_images = []

        # Carry over draft images if present
        if draft_id_to_clean:
            src_dir = os.path.join(draft_images_dir, draft_id_to_clean)
            for att in attachments:
                if att.file_path.startswith(src_dir):
                    fname = os.path.basename(att.file_path)
                    os.makedirs(failed_dir, exist_ok=True)
                    dest = os.path.join(failed_dir, fname)
                    shutil.copy2(att.file_path, dest)
                    failed_images.append({
                        "filename": fname,
                        "alt_text": att.alt_text,
                        "mime_type": att.mime_type,
                    })

        # Save newly uploaded images
        for att in attachments:
            if att.file_path.startswith(config.UPLOAD_FOLDER):
                fname = os.path.basename(att.file_path)
                os.makedirs(failed_dir, exist_ok=True)
                dest = os.path.join(failed_dir, fname)
                shutil.copy2(att.file_path, dest)
                failed_images.append({
                    "filename": fname,
                    "alt_text": att.alt_text,
                    "mime_type": att.mime_type,
                })

        # Clean up originals
        newly_uploaded = [a for a in attachments if a.file_path.startswith(config.UPLOAD_FOLDER)]
        cleanup_uploads(newly_uploaded)
        if draft_id_to_clean:
            old_dir = os.path.join(draft_images_dir, draft_id_to_clean)
            shutil.rmtree(old_dir, ignore_errors=True)

        # Save failed entry with images for retry
        entry = {
            "id": failed_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "text": text,
            "platforms": platform_entries,
            "link_url": link_url or None,
            "image_count": len(failed_images),
            "is_draft": False,
            "is_failed": True,
            "images": failed_images,
        }
        if mode:
            entry["mode"] = mode
            entry["platform_texts"] = platform_texts
        history = _read_history()
        history.insert(0, entry)
        _write_history(history)
    else:
        # Clean up uploaded files (skip draft images — removed separately)
        newly_uploaded = [a for a in attachments if a.file_path.startswith(config.UPLOAD_FOLDER)]
        cleanup_uploads(newly_uploaded)

        # Clean up draft images directory if we used any
        if draft_id_to_clean:
            draft_dir = os.path.join(draft_images_dir, draft_id_to_clean)
            shutil.rmtree(draft_dir, ignore_errors=True)

        # Save to history with platform results
        save_post(
            text=text,
            platforms=platform_entries,
            link_url=link_url,
            image_count=len(attachments),
            is_draft=False,
            mode=mode,
            platform_texts=platform_texts,
        )

    # Update BWE list if this was a BWE mode post
    bwe_name = request.form.get("bwe_site_name", "").strip()
    bwe_url = request.form.get("bwe_site_url", "").strip()
    if mode == "11ty-bwe" and bwe_name and bwe_url:
        platform_letter_map = {"mastodon": "M", "bluesky": "B", "discord": "D"}
        posted_platforms = [
            platform_letter_map[r["platform"]]
            for r in results
            if r["success"] and r["platform"] in platform_letter_map
        ]
        if posted_platforms:
            timestamp = datetime.now(timezone.utc).isoformat()
            update_bwe_after_post(bwe_name, bwe_url, posted_platforms, timestamp)

    return render_template("result.html", results=results)


@app.route("/draft-image/<draft_id>/<filename>")
def draft_image(draft_id, filename):
    draft_dir = os.path.join(_get_path("DRAFT_IMAGES_DIR"), draft_id)
    return send_from_directory(draft_dir, filename)


@app.route("/draft/<draft_id>")
def use_draft(draft_id):
    history = _read_history()
    draft = None
    remaining = []
    for entry in history:
        if entry["id"] == draft_id and entry.get("is_draft"):
            draft = entry
        else:
            remaining.append(entry)
    if draft is None:
        return redirect(url_for("compose"))
    # Remove the draft from history
    _write_history(remaining)
    bwe_to_post, bwe_posted = get_bwe_lists()
    recent = load_recent_posts()
    _annotate_bwe_with_drafts(bwe_to_post, recent)
    return render_template(
        "compose.html",
        mastodon_available=config.mastodon_configured(),
        bluesky_available=config.bluesky_configured(),
        discord_available=config.discord_configured(),
        recent_posts=recent,
        draft=draft,
        modes=all_modes(),
        bwe_to_post=bwe_to_post,
        bwe_posted=bwe_posted,
    )


@app.route("/retry/<post_id>")
def retry_post(post_id):
    history = _read_history()
    failed = None
    remaining = []
    for entry in history:
        if entry["id"] == post_id and (entry.get("is_failed") or (not entry.get("is_draft") and not entry.get("platforms"))):
            failed = entry
        else:
            remaining.append(entry)
    if failed is None:
        return redirect(url_for("compose"))
    # Remove the failed entry from history
    _write_history(remaining)
    bwe_to_post, bwe_posted = get_bwe_lists()
    recent = load_recent_posts()
    _annotate_bwe_with_drafts(bwe_to_post, recent)
    return render_template(
        "compose.html",
        mastodon_available=config.mastodon_configured(),
        bluesky_available=config.bluesky_configured(),
        discord_available=config.discord_configured(),
        recent_posts=recent,
        draft=failed,
        modes=all_modes(),
        bwe_to_post=bwe_to_post,
        bwe_posted=bwe_posted,
    )


@app.route("/draft/<draft_id>/delete", methods=["POST"])
def delete_draft(draft_id):
    return _delete_entry(draft_id)


@app.route("/post/<post_id>/delete", methods=["POST"])
def delete_post(post_id):
    return _delete_entry(post_id)


def _delete_entry(entry_id):
    history = _read_history()
    remaining = []
    for entry in history:
        if entry["id"] == entry_id:
            # Clean up any persisted images
            img_dir = os.path.join(_get_path("DRAFT_IMAGES_DIR"), entry_id)
            shutil.rmtree(img_dir, ignore_errors=True)
        else:
            remaining.append(entry)
    _write_history(remaining)
    return redirect(url_for("compose"))


@app.route("/link-preview", methods=["POST"])
def link_preview():
    data = request.get_json()
    url = data.get("url", "").strip() if data else ""
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    card = fetch_og_metadata(url)
    return jsonify({
        "title": card.title,
        "description": card.description,
        "image_url": card.image_url,
    })


@app.route("/social-links", methods=["POST"])
def social_links():
    data = request.get_json()
    url = data.get("url", "").strip() if data else ""
    if not url:
        return jsonify({"error": "No URL"}), 400
    links = extract_social_links(url)
    return jsonify(links)


@app.route("/create-blog-post", methods=["POST"])
def create_blog_post_route():
    data = request.get_json()
    issue_number = data.get("issue_number") if data else None
    publication_date = data.get("date") if data else None
    if not issue_number:
        return jsonify({"success": False, "error": "No issue number"}), 400
    result = create_blog_post(issue_number, publication_date)
    return jsonify(result)


@app.route("/delete-blog-post", methods=["POST"])
def delete_blog_post_route():
    data = request.get_json()
    issue_number = data.get("issue_number") if data else None
    if not issue_number:
        return jsonify({"success": False, "error": "No issue number"}), 400
    result = delete_blog_post(issue_number)
    return jsonify(result)


@app.route("/edit-blog-post", methods=["POST"])
def edit_blog_post_route():
    data = request.get_json()
    issue_number = data.get("issue_number") if data else None
    if not issue_number:
        return jsonify({"success": False, "error": "No issue number"}), 400
    result = edit_blog_post(issue_number)
    return jsonify(result)


@app.route("/bwe-to-post/delete", methods=["POST"])
def delete_bwe_to_post_entry():
    name = request.form.get("name", "").strip()
    url = request.form.get("url", "").strip()
    if name and url:
        delete_bwe_to_post(name, url)
    return redirect(url_for("compose"))


@app.route("/bwe-posted/delete", methods=["POST"])
def delete_bwe_posted_entry():
    name = request.form.get("name", "").strip()
    url = request.form.get("url", "").strip()
    if name and url:
        delete_bwe_posted(name, url)
    return redirect(url_for("compose"))


@app.route("/editor")
def editor():
    return render_template("editor.html")


@app.route("/editor/check-url", methods=["POST"])
def editor_check_url():
    url = request.json.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    # Normalize: lowercase, strip trailing slashes, ensure protocol, strip www.
    normalized = url.lower().rstrip("/")
    if not normalized.startswith(("http://", "https://")):
        normalized = "https://" + normalized
    normalized = re.sub(r"^(https?://)www\.", r"\1", normalized)

    results = []

    # Check bundledb.json
    try:
        with open(_get_path("BUNDLEDB_PATH"), "r") as f:
            bundledb = json.load(f)
        for entry in bundledb:
            entry_link = (entry.get("Link") or "").strip().lower().rstrip("/")
            if not entry_link.startswith(("http://", "https://")):
                entry_link = "https://" + entry_link
            entry_link = re.sub(r"^(https?://)www\.", r"\1", entry_link)
            if entry_link == normalized:
                results.append({
                    "source": "bundledb.json",
                    "type": entry.get("Type", ""),
                    "title": entry.get("Title", ""),
                    "link": entry.get("Link", ""),
                })
    except Exception:
        pass

    # Check showcase-data.json
    try:
        with open(_get_path("SHOWCASE_PATH"), "r") as f:
            showcase = json.load(f)
        for entry in showcase:
            entry_link = (entry.get("link") or "").strip().lower().rstrip("/")
            if not entry_link.startswith(("http://", "https://")):
                entry_link = "https://" + entry_link
            entry_link = re.sub(r"^(https?://)www\.", r"\1", entry_link)
            if entry_link == normalized:
                results.append({
                    "source": "showcase-data.json",
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                })
    except Exception:
        pass

    return jsonify({"url": url, "found": results})


@app.route("/editor/data")
def editor_data():
    with open(_get_path("BUNDLEDB_PATH"), "r") as f:
        data = json.load(f)

    # For site entries, merge screenshotpath from showcase-data.json
    try:
        with open(_get_path("SHOWCASE_PATH"), "r") as f:
            showcase_data = json.load(f)
        showcase_by_link = {e["link"]: e for e in showcase_data if e.get("link")}
        for item in data:
            if item.get("Type") == "site" and item.get("Link"):
                sc = showcase_by_link.get(item["Link"])
                if sc:
                    item["screenshotpath"] = sc.get("screenshotpath", "")
                    item["leaderboardLink"] = sc.get("leaderboardLink", "")
    except Exception:
        pass

    # Also return showcase data for duplicate link detection
    try:
        with open(_get_path("SHOWCASE_PATH"), "r") as f:
            showcase_list = json.load(f)
    except Exception:
        showcase_list = []

    return jsonify({"bundledb": data, "showcase": showcase_list})


@app.route("/editor/save", methods=["POST"])
def editor_save():
    payload = request.get_json()
    if not payload:
        return jsonify({"success": False, "error": "No data provided"}), 400

    item = payload.get("item")
    is_create = payload.get("create", False)
    backup_created = payload.get("backup_created", False)

    if item is None:
        return jsonify({"success": False, "error": "Missing item"}), 400

    with open(_get_path("BUNDLEDB_PATH"), "r") as f:
        data = json.load(f)

    # Create backup if this is the first save in the session
    if not backup_created:
        _create_backup_with_pruning(_get_path("BUNDLEDB_PATH"), _get_path("BUNDLEDB_BACKUP_DIR"), "bundledb")
        _create_backup_with_pruning(_get_path("SHOWCASE_PATH"), _get_path("SHOWCASE_BACKUP_DIR"), "showcase-data")

    result = {"success": True, "backup_created": True, "propagated": 0}

    if is_create:
        # For site type: add to BWE list and showcase-data.json
        if item.get("Type") == "site":
            title = item.get("Title", "")
            link = item.get("Link", "")
            screenshotpath = item.pop("screenshotpath", "")
            leaderboard_link = item.pop("leaderboardLink", "")

            if title and link:
                try:
                    add_bwe_to_post(title, link)
                    result["bwe_added"] = True
                except Exception:
                    pass

                try:
                    showcase_entry = {
                        "title": title,
                        "description": item.get("description", ""),
                        "link": link,
                        "date": item.get("Date", "")[:10],
                        "formattedDate": item.get("formattedDate", ""),
                        "favicon": item.get("favicon", ""),
                        "screenshotpath": screenshotpath,
                        "leaderboardLink": leaderboard_link,
                    }
                    with open(_get_path("SHOWCASE_PATH"), "r") as f:
                        showcase_data = json.load(f)
                    showcase_data.insert(0, showcase_entry)
                    with open(_get_path("SHOWCASE_PATH"), "w") as f:
                        json.dump(showcase_data, f, indent=2)
                    result["showcase_added"] = True
                except Exception:
                    pass

        data.append(item)
        result["new_index"] = len(data) - 1
    else:
        index = payload.get("index")
        if index is None:
            return jsonify({"success": False, "error": "Missing index"}), 400
        if index < 0 or index >= len(data):
            return jsonify({"success": False, "error": "Index out of range"}), 400

        # For site edits: strip screenshotpath/leaderboardLink from bundledb, sync to showcase-data.json
        if item.get("Type") == "site":
            screenshotpath = item.pop("screenshotpath", "")
            leaderboard_link = item.pop("leaderboardLink", "")
            link = item.get("Link", "")
            if link:
                try:
                    with open(_get_path("SHOWCASE_PATH"), "r") as f:
                        showcase_data = json.load(f)
                    for sc_entry in showcase_data:
                        if sc_entry.get("link") == link:
                            for key in ("title", "description", "favicon"):
                                bundledb_key = "Title" if key == "title" else key
                                sc_entry[key] = item.get(bundledb_key, "")
                            sc_entry["screenshotpath"] = screenshotpath
                            sc_entry["leaderboardLink"] = leaderboard_link
                            sc_entry["date"] = item.get("Date", "")[:10]
                            sc_entry["formattedDate"] = item.get("formattedDate", "")
                            break
                    with open(_get_path("SHOWCASE_PATH"), "w") as f:
                        json.dump(showcase_data, f, indent=2)
                    result["showcase_updated"] = True
                except Exception:
                    pass

        data[index] = item

        # Handle author-level field propagation
        propagate = payload.get("propagate", [])
        propagated = 0
        for entry in propagate:
            p_index = entry.get("index")
            p_field = entry.get("field", "")
            p_value = entry.get("value", "")
            if p_index is None or p_index < 0 or p_index >= len(data):
                continue
            if p_field.startswith("socialLinks."):
                subkey = p_field.split(".", 1)[1]
                if "socialLinks" not in data[p_index]:
                    data[p_index]["socialLinks"] = {}
                data[p_index]["socialLinks"][subkey] = p_value
            else:
                data[p_index][p_field] = p_value
            propagated += 1
        result["propagated"] = propagated

    with open(_get_path("BUNDLEDB_PATH"), "w") as f:
        json.dump(data, f, indent=2)

    return jsonify(result)


@app.route("/editor/delete", methods=["POST"])
def editor_delete():
    payload = request.get_json()
    index = payload.get("index") if payload else None
    backup_created = payload.get("backup_created", False) if payload else False

    if index is None or not isinstance(index, int):
        return jsonify({"success": False, "error": "Missing or invalid index"}), 400

    with open(_get_path("BUNDLEDB_PATH"), "r") as f:
        data = json.load(f)

    if index < 0 or index >= len(data):
        return jsonify({"success": False, "error": "Index out of range"}), 400

    # Create backup if this is the first modification in the session
    if not backup_created:
        _create_backup_with_pruning(_get_path("BUNDLEDB_PATH"), _get_path("BUNDLEDB_BACKUP_DIR"), "bundledb")
        _create_backup_with_pruning(_get_path("SHOWCASE_PATH"), _get_path("SHOWCASE_BACKUP_DIR"), "showcase-data")

    item = data[index]

    # For sites, also remove from showcase-data.json
    if item.get("Type") == "site" and item.get("Link"):
        try:
            with open(_get_path("SHOWCASE_PATH"), "r") as f:
                showcase_data = json.load(f)
            showcase_data = [e for e in showcase_data if e.get("link") != item["Link"]]
            with open(_get_path("SHOWCASE_PATH"), "w") as f:
                json.dump(showcase_data, f, indent=2)
        except Exception:
            pass

    del data[index]

    with open(_get_path("BUNDLEDB_PATH"), "w") as f:
        json.dump(data, f, indent=2)

    return jsonify({"success": True, "backup_created": True})


@app.route("/editor/delete-test-entries", methods=["POST"])
def editor_delete_test_entries():
    payload = request.get_json() or {}
    backup_created = payload.get("backup_created", False)
    marker = "bobdemo99"

    with open(_get_path("BUNDLEDB_PATH"), "r") as f:
        data = json.load(f)

    test_entries = [e for e in data if marker in (e.get("Title") or "").lower()]
    if not test_entries:
        return jsonify({"success": True, "backup_created": backup_created, "deleted": 0})

    # Create backup if first modification in session
    if not backup_created:
        _create_backup_with_pruning(_get_path("BUNDLEDB_PATH"), _get_path("BUNDLEDB_BACKUP_DIR"), "bundledb")
        _create_backup_with_pruning(_get_path("SHOWCASE_PATH"), _get_path("SHOWCASE_BACKUP_DIR"), "showcase-data")

    # Collect links of test site entries for showcase-data cleanup
    test_site_links = {
        e["Link"] for e in test_entries
        if e.get("Type") == "site" and e.get("Link")
    }

    # Remove test entries from bundledb
    remaining = [e for e in data if marker not in (e.get("Title") or "").lower()]
    with open(_get_path("BUNDLEDB_PATH"), "w") as f:
        json.dump(remaining, f, indent=2)

    # Remove matching entries from showcase-data
    if test_site_links:
        try:
            with open(_get_path("SHOWCASE_PATH"), "r") as f:
                showcase_data = json.load(f)
            showcase_data = [
                e for e in showcase_data
                if e.get("link") not in test_site_links
                and marker not in (e.get("title") or "").lower()
            ]
            with open(_get_path("SHOWCASE_PATH"), "w") as f:
                json.dump(showcase_data, f, indent=2)
        except Exception:
            pass

    return jsonify({
        "success": True,
        "backup_created": True,
        "deleted": len(test_entries)
    })


@app.route("/editor/favicon", methods=["POST"])
def editor_favicon():
    data = request.get_json()
    url = data.get("url", "").strip() if data else ""
    if not url:
        return jsonify({"success": False, "error": "No URL provided"}), 400

    from services.favicon import fetch_favicon
    result = fetch_favicon(url)
    if result:
        return jsonify({"success": True, "favicon": result})
    return jsonify({"success": False, "error": "Could not fetch favicon"})


@app.route("/editor/author-info", methods=["POST"])
def editor_author_info():
    """Fetch author site description, social links, favicon, and RSS link."""
    data = request.get_json()
    url = data.get("url", "").strip() if data else ""
    if not url:
        return jsonify({"success": False, "error": "No URL provided"}), 400

    from services.description import extract_description
    from services.social_links import extract_social_links
    from services.favicon import fetch_favicon
    from services.rss_link import extract_rss_link

    result = {"success": True}
    result["description"] = extract_description(url) or ""
    result["socialLinks"] = extract_social_links(url) or {}
    result["favicon"] = fetch_favicon(url) or ""
    result["rssLink"] = extract_rss_link(url) or ""
    return jsonify(result)


@app.route("/editor/description", methods=["POST"])
def editor_description():
    data = request.get_json()
    url = data.get("url", "").strip() if data else ""
    if not url:
        return jsonify({"success": False, "error": "No URL provided"}), 400

    from services.description import extract_description
    description = extract_description(url)
    if description:
        return jsonify({"success": True, "description": description})
    return jsonify({"success": False, "error": "Could not extract description"})


@app.route("/editor/leaderboard", methods=["POST"])
def editor_leaderboard():
    data = request.get_json()
    url = data.get("url", "").strip() if data else ""
    if not url:
        return jsonify({"success": False, "error": "No URL provided"}), 400

    from services.leaderboard import check_leaderboard_link
    result = check_leaderboard_link(url)
    return jsonify({"success": True, "leaderboard_link": result})


@app.route("/editor/screenshot", methods=["POST"])
def editor_screenshot():
    data = request.get_json()
    url = data.get("url", "").strip() if data else ""
    if not url:
        return jsonify({"success": False, "error": "No URL provided"}), 400

    try:
        env = os.environ.copy()
        env["NODE_PATH"] = os.path.join(DBTOOLS_DIR, "node_modules")
        result = subprocess.run(
            ["node", SCREENSHOT_SCRIPT, url],
            cwd=DBTOOLS_DIR,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        output = json.loads(result.stdout.strip())
        return jsonify(output)
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Screenshot timed out"})
    except (json.JSONDecodeError, Exception) as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/editor/end-session", methods=["POST"])
def editor_end_session():
    """Run post-processing scripts to regenerate derived data files."""
    from concurrent.futures import ThreadPoolExecutor

    bundledb_path = _get_path("BUNDLEDB_PATH")
    showcase_path = _get_path("SHOWCASE_PATH")
    bundledb_dir = _get_path("BUNDLEDB_DIR")

    def run_issue_records():
        try:
            output_path = os.path.join(bundledb_dir, "issuerecords.json")
            records = generate_issue_records(bundledb_path, output_path)
            return {"success": True, "stdout": f"Wrote {len(records)} issue records to {output_path}", "stderr": ""}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_latest_data():
        try:
            bundledb_out = os.path.join(bundledb_dir, "bundledb-latest-issue.json")
            showcase_out = os.path.join(bundledb_dir, "showcase-data-latest-issue.json")
            result = generate_latest_data(bundledb_path, showcase_path, bundledb_out, showcase_out)
            return {"success": True, "stdout": f"Latest issue #{result['latest_issue']}: {result['bundledb_count']} bundle entries, {result['showcase_count']} showcase entries", "stderr": ""}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_insights():
        try:
            result = generate_insights(
                bundledb_path=bundledb_path,
                showcase_path=showcase_path,
                exclusions_path=os.path.join(DBTOOLS_DIR, "devdata", "insights-exclusions.json"),
                insights_output_path=os.path.join(bundledb_dir, "insightsdata.json"),
                csv_entry_output_path=os.path.join(ELEVENTY_PROJECT_DIR, "content", "_data", "charts", "entry-growth.csv"),
                csv_author_output_path=os.path.join(ELEVENTY_PROJECT_DIR, "content", "_data", "charts", "author-growth.csv"),
            )
            return {"success": True, "stdout": f"Insights: {result['totalEntries']} entries, {result['blogPosts']} posts, {result['sites']} sites, {result['releases']} releases, {result['totalAuthors']} authors", "stderr": ""}
        except Exception as e:
            return {"success": False, "error": str(e)}

    with ThreadPoolExecutor(max_workers=3) as executor:
        f_issue = executor.submit(run_issue_records)
        f_insights = executor.submit(run_insights)
        f_latest = executor.submit(run_latest_data)

    return jsonify({
        "success": True,
        "genissuerecords": f_issue.result(),
        "generate_insights": f_insights.result(),
        "generate_latest_data": f_latest.result(),
    })


ELEVENTY_PROJECT_DIR = "/Users/Bob/Dropbox/Docs/Sites/11tybundle/11tybundle.dev"

@app.route("/editor/run-latest", methods=["POST"])
def editor_run_latest():
    """Start 'npm run latest' in the 11tybundle.dev project and wait for the server to be ready."""
    import select
    import threading

    try:
        # Kill any existing processes on ports 8080-8083
        for port in (8080, 8081, 8082, 8083):
            try:
                pids = subprocess.check_output(
                    ["lsof", "-ti", f":{port}"], text=True
                ).strip()
                if pids:
                    for pid in pids.split("\n"):
                        subprocess.run(["kill", pid.strip()], check=False)
            except subprocess.CalledProcessError:
                pass  # Nothing listening on this port

        proc = subprocess.Popen(
            ["npm", "run", "latest"],
            cwd=ELEVENTY_PROJECT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        # Watch stdout for Eleventy's server ready message
        deadline = 30  # seconds
        import time
        start = time.time()
        while time.time() - start < deadline:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    return jsonify({"success": False, "error": "Process exited unexpectedly"})
                continue
            if "Server at" in line:
                # Server is ready — drain stdout in a background thread to prevent blocking
                def drain():
                    try:
                        for _ in proc.stdout:
                            pass
                    except Exception:
                        pass
                threading.Thread(target=drain, daemon=True).start()
                return jsonify({"success": True})

        # Timed out waiting for server
        proc.kill()
        return jsonify({"success": False, "error": "Timed out waiting for Eleventy server"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def _commit_and_push_bundledb(commit_message="New entries saved"):
    """Commit and push all changes in the 11tybundledb repo.

    Returns dict with 'success' (bool) and 'message' (str).
    """
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=BUNDLEDB_DIR,
            capture_output=True,
            text=True,
        )
        if not status.stdout.strip():
            return {"success": True, "message": "No DB changes to commit."}

        subprocess.run(["git", "add", "-A"], cwd=BUNDLEDB_DIR, check=True)
        commit = subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=BUNDLEDB_DIR,
            capture_output=True,
            text=True,
        )
        if commit.returncode == 0:
            push = subprocess.run(
                ["git", "push"],
                cwd=BUNDLEDB_DIR,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if push.returncode == 0:
                return {"success": True, "message": "DB files committed and pushed."}
            else:
                return {"success": False, "message": f"git push failed: {push.stderr.strip()}"}
        else:
            return {"success": False, "message": f"git commit failed: {commit.stderr.strip()}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.route("/editor/verify-site", methods=["POST"])
def editor_verify_site():
    """Run post-build verification for entries in the latest issue."""
    from services.verify_site import verify_latest_issue

    try:
        report, success = verify_latest_issue()
        git_result = None
        if success:
            git_result = _commit_and_push_bundledb()
        return jsonify({"success": success, "report": report, "git_result": git_result})
    except Exception as e:
        return jsonify({"success": False, "report": f"Verification error: {e}"})


@app.route("/editor/deploy", methods=["POST"])
def editor_deploy():
    """Run 'npm run deploy' in the 11tybundle.dev project and capture output."""
    try:
        result = subprocess.run(
            ["npm", "run", "deploy"],
            cwd=ELEVENTY_PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        deploy_output = result.stdout + ("\n" + result.stderr if result.stderr else "")
        deploy_success = result.returncode == 0

        if deploy_success:
            git_result = _commit_and_push_bundledb()
        else:
            git_result = {"success": False, "message": "Deploy failed, skipping git."}

        return jsonify({
            "success": deploy_success,
            "output": deploy_output,
            "git_result": git_result,
        })
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "output": "Deploy timed out after 120 seconds."})
    except Exception as e:
        return jsonify({"success": False, "output": str(e)})


@app.route("/editor/screenshot-preview/<filename>")
def editor_screenshot_preview(filename):
    return send_from_directory(SCREENSHOT_DIR, filename)


# ===== Database Management =====

def _compute_db_stats():
    """Compute stats from bundledb.json and showcase-data.json."""
    stats = {"total": 0, "types": {}, "authors": 0, "categories": 0, "showcase_total": 0}
    try:
        with open(_get_path("BUNDLEDB_PATH"), "r") as f:
            data = json.load(f)
        stats["total"] = len(data)
        authors = set()
        categories = set()
        for item in data:
            t = item.get("Type", "unknown")
            stats["types"][t] = stats["types"].get(t, 0) + 1
            if item.get("Author"):
                authors.add(item["Author"])
            for cat in item.get("Categories", []):
                categories.add(cat)
        stats["authors"] = len(authors)
        stats["categories"] = len(categories)
    except Exception:
        pass
    try:
        with open(_get_path("SHOWCASE_PATH"), "r") as f:
            showcase = json.load(f)
        stats["showcase_total"] = len(showcase)
    except Exception:
        pass
    return stats


def _compute_backup_info():
    """Count backup files and find oldest date for each backup directory."""
    info = {}
    for key, prefix in [("bundledb", "bundledb"), ("showcase", "showcase-data")]:
        dir_key = "BUNDLEDB_BACKUP_DIR" if key == "bundledb" else "SHOWCASE_BACKUP_DIR"
        backup_dir = _get_path(dir_key)
        try:
            files = sorted(f for f in os.listdir(backup_dir) if f.startswith(prefix) and f.endswith(".json") and "--" in f)
            oldest = ""
            latest = ""
            if files:
                # Parse date from filename: prefix-YYYY-MM-DD--HHMMSS.json
                for fname, target in [(files[0], "oldest"), (files[-1], "latest")]:
                    name = fname.replace(prefix + "-", "").replace(".json", "")
                    parts = name.split("--")
                    if len(parts) == 2:
                        if target == "oldest":
                            oldest = parts[0]
                        else:
                            latest = parts[0]
            info[key] = {"count": len(files), "oldest": oldest, "latest": latest}
        except Exception:
            info[key] = {"count": 0, "oldest": ""}
    return info


def _find_added_entries(git_dir, sha, filename, title_key):
    """Compare a commit with its parent to find newly added entry titles."""
    try:
        current = subprocess.run(
            ["git", "show", f"{sha}:{filename}"],
            cwd=git_dir, capture_output=True, text=True, timeout=10
        )
        parent = subprocess.run(
            ["git", "show", f"{sha}~1:{filename}"],
            cwd=git_dir, capture_output=True, text=True, timeout=10
        )
        if current.returncode != 0:
            return []
        current_data = json.loads(current.stdout)
        current_titles = {item.get(title_key, "") for item in current_data if item.get(title_key)}
        if parent.returncode != 0:
            return sorted(current_titles)
        parent_data = json.loads(parent.stdout)
        parent_titles = {item.get(title_key, "") for item in parent_data if item.get(title_key)}
        return sorted(current_titles - parent_titles)
    except Exception:
        return []


def _get_commit_history(filename, title_key, count=10):
    """Get recent git commits for a file with added entry titles."""
    git_dir = BUNDLEDB_DIR
    remote_url = "https://github.com/bobmonsour/11tybundledb"
    try:
        result = subprocess.run(
            ["git", "log", f"--format=%H|%aI|%s", f"-{count}", "--", filename],
            cwd=git_dir, capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return []
    except Exception:
        return []

    commits = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        sha, date_str, subject = parts
        added = _find_added_entries(git_dir, sha, filename, title_key)
        commits.append({
            "sha": sha[:7],
            "url": f"{remote_url}/commit/{sha}",
            "date": date_str[:10],
            "subject": subject,
            "added": added,
        })
    return commits


@app.route("/db-mgmt")
def db_mgmt():
    stats = _compute_db_stats()
    backup_info = _compute_backup_info()
    return render_template("db_mgmt.html", stats=stats, backup_info=backup_info)


@app.route("/db-mgmt/commits")
def db_mgmt_commits():
    bundledb_commits = _get_commit_history("bundledb.json", "Title", count=5)
    showcase_commits = _get_commit_history("showcase-data.json", "title", count=5)
    return jsonify({"bundledb": bundledb_commits, "showcase": showcase_commits})


if __name__ == "__main__":
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(os.path.join(_BASE_DIR, "posts"), exist_ok=True)
    os.makedirs(DRAFT_IMAGES_DIR, exist_ok=True)
    app.run(host="127.0.0.1", port=5555, debug=True)
