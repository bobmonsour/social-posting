import json
import os
import shutil
import uuid
from datetime import datetime, timezone

from flask import Flask, redirect, render_template, request, jsonify, url_for, send_from_directory

import config
from modes import all_modes, get_mode
from platforms import get_platform
from platforms.base import LinkCard, MediaAttachment
from services.media import process_uploads, cleanup_uploads, compress_for_bluesky, get_mime_type
from services.link_card import fetch_og_metadata
from services.bwe_list import get_bwe_lists, mark_bwe_posted

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB upload limit

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(_BASE_DIR, "posts", "history.json")
DRAFT_IMAGES_DIR = os.path.join(_BASE_DIR, "posts", "draft_images")


def _read_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r") as f:
        return json.load(f)


def _write_history(entries):
    with open(HISTORY_FILE, "w") as f:
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
    return render_template(
        "compose.html",
        mastodon_available=config.mastodon_configured(),
        bluesky_available=config.bluesky_configured(),
        recent_posts=recent,
        modes=all_modes(),
        bwe_to_post=bwe_to_post,
        bwe_posted=bwe_posted,
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
        for pname in ["mastodon", "bluesky"]:
            pt = request.form.get(f"text_{pname}", "").strip()
            if pt:
                platform_texts[pname] = pt

    if not text and not (mode and platform_texts):
        return render_template(
            "result.html",
            results=[{"platform": "error", "success": False, "error": "No text provided"}],
        )

    # --- Draft path: save and redirect, skip posting ---
    if is_draft:
        # Process any newly uploaded images
        files = request.files.getlist("images")
        alt_texts = [request.form.get(f"alt_text_{i}", "") for i in range(4)]
        attachments = process_uploads(files, alt_texts)

        # Generate draft ID and save images to persistent storage
        draft_id = str(uuid.uuid4())
        draft_images = []
        draft_dir = os.path.join(DRAFT_IMAGES_DIR, draft_id)

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
                    src = os.path.join(DRAFT_IMAGES_DIR, old_did, fname)
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
            old_dir = os.path.join(DRAFT_IMAGES_DIR, old_draft_id)
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
                    img_dir = os.path.join(DRAFT_IMAGES_DIR, old["id"])
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
                fpath = os.path.join(DRAFT_IMAGES_DIR, did, fname)
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
        failed_dir = os.path.join(DRAFT_IMAGES_DIR, failed_id)
        failed_images = []

        # Carry over draft images if present
        if draft_id_to_clean:
            src_dir = os.path.join(DRAFT_IMAGES_DIR, draft_id_to_clean)
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
            old_dir = os.path.join(DRAFT_IMAGES_DIR, draft_id_to_clean)
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
            draft_dir = os.path.join(DRAFT_IMAGES_DIR, draft_id_to_clean)
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
        status_parts = []
        for r in results:
            if r["success"]:
                status_parts.append(f"Posted to {r['platform'].title()}")
            else:
                status_parts.append(f"Failed to post to {r['platform'].title()}")
        timestamp = datetime.now(timezone.utc).isoformat()
        mark_bwe_posted(bwe_name, bwe_url, timestamp, ", ".join(status_parts))

    return render_template("result.html", results=results)


@app.route("/draft-image/<draft_id>/<filename>")
def draft_image(draft_id, filename):
    draft_dir = os.path.join(DRAFT_IMAGES_DIR, draft_id)
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
            img_dir = os.path.join(DRAFT_IMAGES_DIR, entry_id)
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


if __name__ == "__main__":
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(os.path.join(_BASE_DIR, "posts"), exist_ok=True)
    os.makedirs(DRAFT_IMAGES_DIR, exist_ok=True)
    app.run(host="127.0.0.1", port=5555, debug=True)
