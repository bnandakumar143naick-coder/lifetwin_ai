"""Shared doctor<->patient messaging logic (database-backed, HTTP polling)."""
from datetime import datetime

from flask import render_template, request, redirect, flash
from flask_login import current_user

from models import db
from models_ecosystem import Message, N_DOCUMENT
from ecosystem.files import save_attachment
from ecosystem.notify import notify, notify_message_once

MAX_LEN = 2000


def mark_thread_read(conv):
    now = datetime.utcnow()
    unread = Message.query.filter(Message.conversation_id == conv.id,
                                  Message.sender_user_id != current_user.id,
                                  Message.is_read == False).all()  # noqa: E712
    for m in unread:
        m.is_read, m.read_at = True, now
    if unread:
        db.session.commit()


def send_from_request(conv, recipient_user_id, recipient_link, sender_label):
    """Validate and store a message (+ optional attachment). Returns True on success."""
    text = (request.form.get("message", "") or "").strip()
    upload = request.files.get("attachment")
    has_file = bool(upload and upload.filename)

    if not text and not has_file:
        flash("Type a message or attach a file.", "error")
        return False
    if len(text) > MAX_LEN:
        flash(f"Message is too long (max {MAX_LEN} characters).", "error")
        return False

    stored = original = mime = None
    if has_file:
        try:
            stored, original, mime = save_attachment(upload)
        except ValueError as e:
            flash(str(e), "error")
            return False

    msg = Message(conversation_id=conv.id, sender_user_id=current_user.id, message=text,
                  attachment_stored_name=stored, attachment_original_name=original, attachment_mime=mime)
    db.session.add(msg)
    db.session.flush()

    preview = text[:80] + ("…" if len(text) > 80 else "")
    notify_message_once(recipient_user_id, conv.id,
                        f"New message from {sender_label}" + (f": {preview}" if preview else " (attachment)"),
                        recipient_link)
    if has_file:
        notify(recipient_user_id, N_DOCUMENT, f"{sender_label} shared a document: {original}", link=recipient_link)
    db.session.commit()
    return True


def render_thread(conv, other_name, other_subtitle, post_url, back_url):
    mark_thread_read(conv)
    return render_template("chat.html", conv=conv, messages=conv.messages, other_name=other_name,
                           other_subtitle=other_subtitle, post_url=post_url, back_url=back_url,
                           last_id=(conv.messages[-1].id if conv.messages else 0))
