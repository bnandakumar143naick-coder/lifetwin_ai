"""
Hooks called by the ORIGINAL patient routes (one line each in app.py).
They are wrapped so that a failure here can NEVER break the original patient flow:
on any error the notification work is rolled back and logged, and the patient's
already-committed data is untouched.
"""
from flask import current_app

from models import db
from ecosystem import notify as N


def _safe(fn, *args):
    try:
        fn(*args)
        db.session.commit()
    except Exception:  # pragma: no cover - defensive
        db.session.rollback()
        current_app.logger.exception("ecosystem hook failed: %s", getattr(fn, "__name__", fn))


def after_vitals_saved(user, vitals, alerts):
    _safe(N.notify_vitals_recorded, user, vitals, alerts)


def after_lab_saved(user, lab):
    _safe(N.notify_lab_recorded, user, lab)


def after_symptoms_saved(user, log):
    _safe(N.notify_symptoms_recorded, user, log)


def after_profile_saved(user):
    _safe(N.record_weight, user)
