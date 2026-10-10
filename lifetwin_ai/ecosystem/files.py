"""Secure attachment handling. Files live under instance/attachments (never in
static/) with random server-side names and are served only by authorized routes."""
import os
import secrets

from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".docx"}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB

_MIME = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
         ".jpeg": "image/jpeg",
         ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def attachments_dir():
    d = current_app.config.get("ATTACHMENTS_DIR") or os.path.join(current_app.root_path, "instance", "attachments")
    os.makedirs(d, exist_ok=True)
    return d


def _magic_ok(ext, head):
    if ext == ".pdf":
        return head.startswith(b"%PDF")
    if ext == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in (".jpg", ".jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext == ".docx":
        return head.startswith(b"PK")
    return False


def save_attachment(file_storage):
    """Validate + store. Returns (stored_name, original_name, mime). Raises ValueError."""
    original = secure_filename(file_storage.filename or "")
    if not original:
        raise ValueError("Invalid attachment name.")
    ext = os.path.splitext(original)[1].lower()
    if ext not in ALLOWED_EXT:
        raise ValueError("Attachment type not allowed. Use PDF, PNG, JPG or DOCX.")

    stream = file_storage.stream
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)
    if size == 0:
        raise ValueError("The attachment is empty.")
    if size > MAX_BYTES:
        raise ValueError("Attachment is too large (max 5 MB).")
    head = stream.read(16)
    stream.seek(0)
    if not _magic_ok(ext, head):
        raise ValueError("The file content does not match its extension.")

    stored = secrets.token_hex(16) + ext
    file_storage.save(os.path.join(attachments_dir(), stored))
    return stored, original, _MIME[ext]


def attachment_path(stored_name):
    # stored names are server-generated hex + ext; still refuse anything path-like
    if not stored_name or os.path.basename(stored_name) != stored_name:
        return None
    p = os.path.join(attachments_dir(), stored_name)
    return p if os.path.isfile(p) else None
