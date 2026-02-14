import os
import uuid

from PIL import Image
from werkzeug.utils import secure_filename

import config
from platforms.base import MediaAttachment


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in config.ALLOWED_EXTENSIONS
    )


def get_mime_type(file_path):
    try:
        img = Image.open(file_path)
        fmt = img.format.lower()
        mime_map = {
            "jpeg": "image/jpeg",
            "jpg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
        }
        return mime_map.get(fmt, "image/jpeg")
    except Exception:
        return "image/jpeg"


def compress_for_bluesky(file_path, mime_type):
    """Compress image to fit under Bluesky's 1MB limit. Returns new path."""
    file_size = os.path.getsize(file_path)
    if file_size <= config.BLUESKY_MAX_IMAGE_SIZE:
        return file_path

    img = Image.open(file_path)

    # Convert to RGB if needed (for JPEG saving)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Progressively reduce quality
    quality = 85
    while quality >= 20:
        compressed_path = file_path + ".compressed.jpg"
        img.save(compressed_path, "JPEG", quality=quality, optimize=True)
        if os.path.getsize(compressed_path) <= config.BLUESKY_MAX_IMAGE_SIZE:
            return compressed_path
        os.remove(compressed_path)
        quality -= 10

    # Last resort: resize
    max_dim = 2048
    while max_dim >= 512:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)
        compressed_path = file_path + ".compressed.jpg"
        img.save(compressed_path, "JPEG", quality=60, optimize=True)
        if os.path.getsize(compressed_path) <= config.BLUESKY_MAX_IMAGE_SIZE:
            return compressed_path
        os.remove(compressed_path)
        max_dim -= 512

    return file_path


def save_upload(file_storage):
    """Save an uploaded file to the uploads directory. Returns the file path."""
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        return None

    filename = secure_filename(file_storage.filename)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    file_path = os.path.join(config.UPLOAD_FOLDER, unique_name)
    file_storage.save(file_path)
    return file_path


def process_uploads(files, alt_texts):
    """Process uploaded files into MediaAttachment list."""
    attachments = []
    for i, f in enumerate(files):
        if not f or not f.filename:
            continue
        file_path = save_upload(f)
        if file_path is None:
            continue
        mime_type = get_mime_type(file_path)
        alt_text = alt_texts[i] if i < len(alt_texts) else ""
        attachments.append(
            MediaAttachment(
                file_path=file_path,
                mime_type=mime_type,
                alt_text=alt_text,
            )
        )
        if len(attachments) >= config.MAX_IMAGES:
            break
    return attachments


def cleanup_uploads(attachments):
    """Remove uploaded files after posting."""
    for att in attachments:
        try:
            os.remove(att.file_path)
        except OSError:
            pass
        # Also remove any compressed versions
        compressed = att.file_path + ".compressed.jpg"
        try:
            os.remove(compressed)
        except OSError:
            pass
