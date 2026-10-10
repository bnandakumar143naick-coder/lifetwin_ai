"""Routes shared by all roles: notifications, account, attachments, chat polling."""
from datetime import datetime

from flask import (Blueprint, render_template, request, redirect, url_for, flash,
                   abort, jsonify, send_file)
from flask_login import login_required, current_user

from models import db
from models_ecosystem import (
    Notification, Message, Conversation, FamilyMember,
    ROLE_PATIENT, ROLE_DOCTOR, ROLE_FAMILY,
)
from ecosystem.access import (
    authorize_conversation_participant, get_connection, family_can,
)
from ecosystem.files import attachment_path
from ecosystem.security import role_home_url, role_required

bp = Blueprint("common", __name__)


# ---------------- notifications ----------------
@bp.route("/notifications")
@role_required(ROLE_PATIENT, ROLE_DOCTOR, ROLE_FAMILY)
def notifications():
    items = (Notification.query.filter_by(user_id=current_user.id)
             .order_by(Notification.id.desc()).limit(100).all())
    return render_template("notifications.html", items=items)


@bp.route("/notifications/<int:nid>/open", methods=["POST"])
@role_required(ROLE_PATIENT, ROLE_DOCTOR, ROLE_FAMILY)
def notification_open(nid):
    n = db.session.get(Notification, nid)
    if not n or n.user_id != current_user.id:
        abort(403)
    n.is_read = True
    db.session.commit()
    target = n.link if (n.link and n.link.startswith("/") and not n.link.startswith("//")) else url_for("common.notifications")
    return redirect(target)


@bp.route("/notifications/read-all", methods=["POST"])
@role_required(ROLE_PATIENT, ROLE_DOCTOR, ROLE_FAMILY)
def notifications_read_all():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("common.notifications"))


# ---------------- account ----------------
@bp.route("/account", methods=["GET", "POST"])
@role_required(ROLE_PATIENT, ROLE_DOCTOR, ROLE_FAMILY)
def account():
    if request.method == "POST":
        current_pw = request.form.get("current_password", "")
        new_pw = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        phone = request.form.get("phone", "").strip()[:30]
        if phone != (current_user.phone or ""):
            current_user.phone = phone or None
        if new_pw:
            if not current_user.check_password(current_pw):
                flash("Current password is incorrect.", "error")
                return redirect(url_for("common.account"))
            if len(new_pw) < 8:
                flash("New password must be at least 8 characters.", "error")
                return redirect(url_for("common.account"))
            if new_pw != confirm:
                flash("New password and confirmation do not match.", "error")
                return redirect(url_for("common.account"))
            current_user.set_password(new_pw)
        db.session.commit()
        flash("Account updated.", "success")
        return redirect(url_for("common.account"))
    return render_template("account.html")


# ---------------- attachments (authorized download only) ----------------
@bp.route("/attachments/<int:message_id>")
@role_required(ROLE_PATIENT, ROLE_DOCTOR)
def attachment_download(message_id):
    msg = db.session.get(Message, message_id)
    if not msg or not msg.attachment_stored_name:
        abort(403)
    authorize_conversation_participant(msg.conversation)  # must be the doctor or patient of an ACCEPTED link
    path = attachment_path(msg.attachment_stored_name)
    if not path:
        abort(404)
    return send_file(path, as_attachment=True, download_name=msg.attachment_original_name or "attachment",
                     mimetype=msg.attachment_mime or "application/octet-stream")


# ---------------- chat polling (normal HTTP polling — NOT websockets) ----------------
def _serialize(m, viewer_id):
    return {
        "id": m.id, "mine": m.sender_user_id == viewer_id,
        "sender": m.sender.full_name, "message": m.message,
        "time": m.created_at.strftime("%d %b %H:%M"), "is_read": bool(m.is_read),
        "attachment": ({"name": m.attachment_original_name,
                        "url": url_for("common.attachment_download", message_id=m.id)}
                       if m.attachment_stored_name else None),
    }


@bp.route("/api/conversations/<int:conv_id>/messages")
@role_required(ROLE_PATIENT, ROLE_DOCTOR)
def api_messages(conv_id):
    conv = db.session.get(Conversation, conv_id)
    authorize_conversation_participant(conv)
    after = request.args.get("after", 0, type=int)
    msgs = Message.query.filter(Message.conversation_id == conv.id, Message.id > after).order_by(Message.id).all()
    changed = False
    for m in msgs:
        if m.sender_user_id != current_user.id and not m.is_read:
            m.is_read, m.read_at, changed = True, datetime.utcnow(), True
    if changed:
        db.session.commit()
    # read-receipt info for messages I sent
    my_read = [x.id for x in Message.query.filter_by(conversation_id=conv.id, sender_user_id=current_user.id,
                                                    is_read=True).all()]
    return jsonify({"messages": [_serialize(m, current_user.id) for m in msgs], "my_read_ids": my_read})
