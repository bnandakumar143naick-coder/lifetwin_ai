"""
Notification + emergency fan-out.

The emergency DETECTION is still utils.emergency.check_emergency (unchanged).
This module only decides WHO is told once that engine has produced alerts:
    patient  +  ACCEPTED (verified) doctors  +  family with emergency_alerts=True
Notifications are in-app records. No SMS/e-mail/emergency-service contact is made.
"""
from datetime import datetime

from models import db
from models_ecosystem import (
    Notification, EmergencyEvent, FamilyMember, FamilyPermission,
    N_CONNECTION, N_MESSAGE, N_DOCUMENT, N_EMERGENCY, N_HEALTH_UPDATE, N_FAMILY_ACCESS,
)
from ecosystem.access import accepted_doctors_for_patient

EMERGENCY_DISCLAIMER = ("This is an automated threshold alert, not a diagnosis. "
                        "It does not replace a doctor or emergency services.")


def notify(user_id, ntype, message, link=None, related_id=None, commit=False):
    n = Notification(user_id=user_id, notification_type=ntype,
                     message=message[:500], link=link, related_id=related_id)
    db.session.add(n)
    if commit:
        db.session.commit()
    return n


def notify_message_once(user_id, conv_id, message, link):
    """Coalesce chat notifications: at most one UNREAD per conversation."""
    existing = Notification.query.filter_by(
        user_id=user_id, notification_type=N_MESSAGE, related_id=conv_id, is_read=False).first()
    if existing:
        existing.message = message[:500]
        existing.created_at = datetime.utcnow()
        return existing
    return notify(user_id, N_MESSAGE, message, link=link, related_id=conv_id)


def _family_with(patient_id, flag):
    rows = (FamilyMember.query.join(FamilyPermission,
            FamilyPermission.family_member_id == FamilyMember.id)
            .filter(FamilyMember.patient_id == patient_id)
            .filter(getattr(FamilyPermission, flag) == True)  # noqa: E712
            .all())
    return rows


# ---------------- emergency ----------------
def dispatch_emergency(patient, vitals, alerts):
    """Create the EmergencyEvent + notification records for every authorized party."""
    doctors = accepted_doctors_for_patient(patient.id)
    family = _family_with(patient.id, "emergency_alerts")

    doc_names = [f"Dr. {d.user.full_name}" for d in doctors]
    fam_names = [f"{f.member_user.full_name} ({f.relationship_label})" for f in family]
    summary = []
    if doc_names:
        summary.append("Doctor(s): " + ", ".join(doc_names))
    if fam_names:
        summary.append("Family: " + ", ".join(fam_names))

    event = EmergencyEvent(patient_id=patient.id, vital_id=getattr(vitals, "id", None),
                           details="\n".join(alerts),
                           notified_summary=" | ".join(summary) or "No doctors or family members are linked")
    db.session.add(event)

    first = alerts[0]
    notify(patient.id, N_EMERGENCY,
           f"🚨 Emergency threshold detected: {first}. Consider seeking medical care now. "
           f"{('Notified: ' + event.notified_summary + '. ') if summary else ''}{EMERGENCY_DISCLAIMER}",
           link="/emergency")
    for d in doctors:
        notify(d.user_id, N_EMERGENCY,
               f"🚨 Emergency alert — {patient.full_name}: {first}. {EMERGENCY_DISCLAIMER}",
               link=f"/doctor/patient/{patient.id}")
    for f in family:
        notify(f.user_id, N_EMERGENCY,
               f"🚨 Emergency alert for {patient.full_name}: {first}. {EMERGENCY_DISCLAIMER}",
               link=f"/family/alerts?fm={f.id}")
    return event


# ---------------- hooks called from the (unchanged-logic) patient routes ----------------
def notify_vitals_recorded(patient, vitals, alerts):
    if alerts:
        dispatch_emergency(patient, vitals, alerts)
        return
    for d in accepted_doctors_for_patient(patient.id):
        notify(d.user_id, N_HEALTH_UPDATE, f"New vitals from {patient.full_name}.",
               link=f"/doctor/patient/{patient.id}")
    for f in _family_with(patient.id, "view_vitals"):
        notify(f.user_id, N_HEALTH_UPDATE, f"{patient.full_name} recorded new vital signs.",
               link=f"/family/vitals?fm={f.id}")


def notify_lab_recorded(patient, lab):
    has_file = bool(getattr(lab, "file_path", None))
    for d in accepted_doctors_for_patient(patient.id):
        if has_file:
            notify(d.user_id, N_DOCUMENT, f"{patient.full_name} uploaded a lab report document.",
                   link=f"/doctor/patient/{patient.id}/timeline")
        else:
            notify(d.user_id, N_HEALTH_UPDATE, f"New lab values from {patient.full_name}.",
                   link=f"/doctor/patient/{patient.id}")
    for f in _family_with(patient.id, "view_labs"):
        notify(f.user_id, N_HEALTH_UPDATE, f"{patient.full_name} added new lab results.",
               link=f"/family/health?fm={f.id}")


def notify_symptoms_recorded(patient, log):
    for d in accepted_doctors_for_patient(patient.id):
        notify(d.user_id, N_HEALTH_UPDATE, f"{patient.full_name} logged new symptoms.",
               link=f"/doctor/patient/{patient.id}")
    for f in _family_with(patient.id, "view_symptoms"):
        notify(f.user_id, N_HEALTH_UPDATE, f"{patient.full_name} logged new symptoms.",
               link=f"/family/health?fm={f.id}")


def record_weight(user):
    """Called after the health profile is saved (weight history for trends)."""
    from models_ecosystem import ProfileWeightLog
    if user.profile and user.profile.weight_kg:
        last = (ProfileWeightLog.query.filter_by(user_id=user.id)
                .order_by(ProfileWeightLog.id.desc()).first())
        if not last or last.weight_kg != user.profile.weight_kg:
            db.session.add(ProfileWeightLog(user_id=user.id, weight_kg=user.profile.weight_kg))
