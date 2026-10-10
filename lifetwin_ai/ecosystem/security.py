"""
Backend-enforced security primitives: role checks, CSRF (for new routes),
security headers and a guard that keeps non-patient roles out of legacy
patient-only pages WITHOUT editing those legacy routes.
"""
import hmac
import secrets
from functools import wraps
from urllib.parse import urlparse

from flask import abort, redirect, request, session, url_for, flash, jsonify
from flask_login import current_user

from models_ecosystem import ROLE_PATIENT, ROLE_DOCTOR, ROLE_FAMILY

# Endpoints of the ORIGINAL patient app. Only PATIENT users may use them.
LEGACY_PATIENT_ENDPOINTS = {
    "dashboard", "edit_profile", "data_entry", "labs", "symptoms",
    "coach", "coach_ask", "download_report",
}

# Blueprint names that belong to the ecosystem (CSRF + no-store apply here).
ECOSYSTEM_BLUEPRINTS = {"eco_auth", "doctor", "pt", "family", "common"}


def role_home_url(user):
    if user.role == ROLE_DOCTOR:
        return url_for("doctor.dashboard")
    if user.role == ROLE_FAMILY:
        return url_for("family.dashboard")
    return url_for("dashboard")


def role_required(*roles):
    """Login + role gate enforced on the server."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "authentication required"}), 401
                flash("Please log in to continue.", "info")
                target = "login"
                if ROLE_DOCTOR in roles and len(roles) == 1:
                    target = "eco_auth.doctor_login"
                elif ROLE_FAMILY in roles and len(roles) == 1:
                    target = "eco_auth.family_login"
                return redirect(url_for(target))
            if current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return deco


# ---------------- CSRF (new routes only; legacy forms are untouched) ----------------
def get_csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def _csrf_check():
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if request.blueprint not in ECOSYSTEM_BLUEPRINTS:
        return
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
    expected = session.get("_csrf_token") or ""
    if not expected or not hmac.compare_digest(sent, expected):
        abort(400, description="Your session expired or the form was invalid. Please go back, refresh and try again.")


def _legacy_role_guard():
    if request.endpoint in LEGACY_PATIENT_ENDPOINTS and current_user.is_authenticated:
        if current_user.role != ROLE_PATIENT:
            if request.endpoint == "coach_ask":
                return jsonify({"error": "forbidden"}), 403
            return redirect(role_home_url(current_user))


def _security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if request.blueprint in ECOSYSTEM_BLUEPRINTS and current_user.is_authenticated:
        response.headers["Cache-Control"] = "no-store"
    return response


def safe_next_url(default):
    """Only allow same-site relative redirects."""
    nxt = request.args.get("next") or request.form.get("next")
    if nxt:
        p = urlparse(nxt)
        if not p.netloc and not p.scheme and nxt.startswith("/") and not nxt.startswith("//"):
            return nxt
    return default


def install_security(app):
    app.before_request(_csrf_check)
    app.before_request(_legacy_role_guard)
    app.after_request(_security_headers)
    app.jinja_env.globals["csrf_token"] = get_csrf_token
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
