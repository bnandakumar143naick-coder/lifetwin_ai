"""
LifeTwin AI - Patient + Doctor + Family ecosystem (extension package).

Everything here is ADDED next to the original app. The original engines in utils/
and the original patient routes in app.py are reused, not replaced.
"""
import os

from flask import render_template, request, jsonify, current_app
from flask_login import current_user

from models import db
from models_ecosystem import Message, Conversation, Notification, ROLE_DOCTOR, ROLE_PATIENT, ROLE_FAMILY

from ecosystem.schema import ensure_ecosystem_schema  # noqa: F401  (re-exported for app.py)
from ecosystem.hooks import (  # noqa: F401  (re-exported for app.py)
    after_vitals_saved, after_lab_saved, after_symptoms_saved, after_profile_saved,
)


def _context_processor():
    ctx = {"nav_role": None, "unread_notifications": 0, "unread_messages": 0, "fam_fm": None}
    if not current_user.is_authenticated:
        return ctx
    ctx["nav_role"] = current_user.role or ROLE_PATIENT
    try:
        ctx["unread_notifications"] = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        if current_user.role == ROLE_DOCTOR and current_user.doctor_profile:
            q = (db.session.query(Message).join(Conversation, Message.conversation_id == Conversation.id)
                 .filter(Conversation.doctor_id == current_user.doctor_profile.id,
                         Message.sender_user_id != current_user.id, Message.is_read == False))  # noqa: E712
            ctx["unread_messages"] = q.count()
        elif current_user.role == ROLE_PATIENT:
            q = (db.session.query(Message).join(Conversation, Message.conversation_id == Conversation.id)
                 .filter(Conversation.patient_id == current_user.id,
                         Message.sender_user_id != current_user.id, Message.is_read == False))  # noqa: E712
            ctx["unread_messages"] = q.count()
        elif current_user.role == ROLE_FAMILY:
            from ecosystem.family_routes import resolve_active_link_id
            ctx["fam_fm"] = resolve_active_link_id()
    except Exception:  # never let nav badges break a page
        db.session.rollback()
    return ctx


def _register_error_pages(app):
    messages = {
        400: ("Request could not be processed", None),
        403: ("Access denied", "You don't have permission to view this page, or it doesn't exist."),
        404: ("Page not found", "We couldn't find what you were looking for."),
        413: ("File too large", "The uploaded file is too large."),
        500: ("Something went wrong", "An unexpected error occurred. Your data was not changed. Please try again."),
    }

    def make(code):
        def handler(err):
            if code == 500:
                db.session.rollback()
            title, default = messages[code]
            desc = getattr(err, "description", None)
            detail = desc if (code == 400 and desc) else default
            if request.path.startswith("/api/"):
                return jsonify({"error": title}), code
            return render_template("error.html", code=code, title=title, detail=detail), code
        return handler

    for code in messages:
        app.register_error_handler(code, make(code))


def register_ecosystem(app):
    from ecosystem.security import install_security
    from ecosystem import auth_routes, common_routes, doctor_routes, patient_routes, family_routes
    from ecosystem.cli import register_cli

    app.config.setdefault("AUTO_VERIFY_DOCTORS", os.environ.get("LIFETWIN_AUTO_VERIFY_DOCTORS", "0") == "1")
    app.config.setdefault("ATTACHMENTS_DIR", os.path.join(app.root_path, "instance", "attachments"))
    app.config.setdefault("MAX_CONTENT_LENGTH", 12 * 1024 * 1024)
    os.makedirs(app.config["ATTACHMENTS_DIR"], exist_ok=True)

    install_security(app)
    for mod in (auth_routes, common_routes, doctor_routes, patient_routes, family_routes):
        app.register_blueprint(mod.bp)
    app.context_processor(_context_processor)
    _register_error_pages(app)
    register_cli(app)
