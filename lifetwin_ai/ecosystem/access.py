"""
Server-side authorization. EVERY route that touches another person's data
goes through one of these helpers. Frontend hiding is never relied upon.

Policy summary
--------------
Doctor  -> patient data only if: doctor is VERIFIED and connection is ACCEPTED.
Family  -> only the patient who linked them, and only flags in FamilyPermission.
Patient -> only their own data.
Unauthorized and missing targets both return 403 (indistinguishable, so IDs
cannot be enumerated).
"""
from flask import abort
from flask_login import current_user

from models import db, User
from models_ecosystem import (
    Doctor, DoctorPatientConnection, Conversation, FamilyMember,
    CONN_ACCEPTED, ROLE_PATIENT, ROLE_DOCTOR, ROLE_FAMILY,
)


# ---------------- doctor side ----------------
def current_doctor_or_403():
    if not current_user.is_authenticated or current_user.role != ROLE_DOCTOR:
        abort(403)
    doc = current_user.doctor_profile
    if not doc:
        abort(403)
    return doc


def get_connection(doctor_id, patient_id):
    return DoctorPatientConnection.query.filter_by(doctor_id=doctor_id, patient_id=patient_id).first()


def doctor_has_access(doctor, patient_id):
    if not doctor or not doctor.is_verified:
        return False
    conn = get_connection(doctor.id, patient_id)
    return bool(conn and conn.status == CONN_ACCEPTED)


def authorize_doctor_for_patient(patient_id):
    """Return the patient User the current doctor may view, else abort(403)."""
    doctor = current_doctor_or_403()
    if not doctor_has_access(doctor, patient_id):
        abort(403)
    patient = db.session.get(User, patient_id)
    if not patient or patient.role != ROLE_PATIENT:
        abort(403)
    return doctor, patient


def accepted_patient_ids(doctor):
    rows = DoctorPatientConnection.query.filter_by(doctor_id=doctor.id, status=CONN_ACCEPTED).all()
    return [r.patient_id for r in rows]


def accepted_doctors_for_patient(patient_id):
    """Verified doctors currently connected (ACCEPTED) to this patient."""
    rows = (DoctorPatientConnection.query
            .filter_by(patient_id=patient_id, status=CONN_ACCEPTED).all())
    return [r.doctor for r in rows if r.doctor and r.doctor.is_verified]


# ---------------- conversations ----------------
def get_or_create_conversation(doctor_id, patient_id):
    conv = Conversation.query.filter_by(doctor_id=doctor_id, patient_id=patient_id).first()
    if not conv:
        conv = Conversation(doctor_id=doctor_id, patient_id=patient_id)
        db.session.add(conv)
        db.session.flush()
    return conv


def authorize_conversation_participant(conv):
    """Only the doctor or patient of an ACCEPTED connection may use a conversation."""
    if not conv:
        abort(403)
    conn = get_connection(conv.doctor_id, conv.patient_id)
    if not conn or conn.status != CONN_ACCEPTED or not conv.doctor.is_verified:
        abort(403)
    if current_user.role == ROLE_PATIENT and current_user.id == conv.patient_id:
        return "patient"
    if current_user.role == ROLE_DOCTOR and current_user.doctor_profile \
            and current_user.doctor_profile.id == conv.doctor_id:
        return "doctor"
    abort(403)


# ---------------- family side ----------------
def family_link_or_403(fm_id):
    """The FamilyMember link must belong to the logged-in FAMILY user."""
    if not current_user.is_authenticated or current_user.role != ROLE_FAMILY:
        abort(403)
    fm = db.session.get(FamilyMember, fm_id) if fm_id else None
    if not fm or fm.user_id != current_user.id or not fm.permission:
        abort(403)
    if not fm.patient or fm.patient.role != ROLE_PATIENT:
        abort(403)
    return fm


def family_can(fm, flag):
    return bool(fm and fm.permission and getattr(fm.permission, flag, False))


def family_require(fm, flag):
    if not family_can(fm, flag):
        abort(403)
    return fm


def family_links_for_current_user():
    return (FamilyMember.query.filter_by(user_id=current_user.id)
            .order_by(FamilyMember.id).all())
