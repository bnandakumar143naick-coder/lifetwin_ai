"""Family portal. Access is limited to the linking patient and to the flags in FamilyPermission.
Each route hands the template ONLY permitted data (never relies on hiding things in HTML)."""
from flask import Blueprint, render_template, request, redirect, url_for, abort
from flask_login import current_user

from models_ecosystem import (
    Conversation, EmergencyEvent, ROLE_FAMILY,
)
from ecosystem.security import role_required
from ecosystem.access import (
    family_link_or_403, family_can, family_require, family_links_for_current_user,
    accepted_doctors_for_patient,
)
from ecosystem.twin import compute_twin
from ecosystem.timeline import build_timeline
from utils.emergency import check_emergency

bp = Blueprint("family", __name__, url_prefix="/family")


def resolve_active_link_id():
    """Used by the nav (context processor) and by every route."""
    links = family_links_for_current_user()
    if not links:
        return None
    wanted = request.args.get("fm", type=int)
    ids = {l.id for l in links}
    return wanted if wanted in ids else links[0].id


def _link():
    links = family_links_for_current_user()
    if not links:
        return None, links
    fm = family_link_or_403(resolve_active_link_id())
    return fm, links


def _allowed_timeline_kinds(fm):
    kinds = set()
    if family_can(fm, "view_vitals"):
        kinds.add("vitals")
    if family_can(fm, "view_labs"):
        kinds.add("labs")
    if family_can(fm, "view_symptoms"):
        kinds.add("symptoms")
    if family_can(fm, "view_health_score"):
        kinds.add("score")
    if family_can(fm, "emergency_alerts"):
        kinds.add("emergency")
    return kinds


@bp.route("/dashboard")
@role_required(ROLE_FAMILY)
def dashboard():
    fm, links = _link()
    if not fm:
        return render_template("family_dashboard.html", fm=None, links=[], view=None)
    patient = fm.patient
    twin = compute_twin(patient)
    view = {"patient_name": patient.full_name, "relationship": fm.relationship_label}
    perm = fm.permission
    if perm.view_health_score and twin:
        view["score"] = twin["scores"]["overall"]
    if perm.view_vitals and twin and twin["vitals"]:
        v = twin["vitals"]
        view["vitals"] = {"bp": f"{v.systolic_bp or '-'}/{v.diastolic_bp or '-'}", "hr": v.heart_rate,
                          "spo2": v.oxygen_saturation, "when": v.recorded_at}
    kinds = _allowed_timeline_kinds(fm)
    latest = build_timeline(patient, allowed=kinds, limit=1) if kinds else []
    view["latest_update"] = latest[0] if latest else None
    if perm.emergency_alerts:
        lv = patient.vitals[-1] if patient.vitals else None
        view["emergency_now"] = check_emergency(lv)
    if perm.view_doctor_conversations:
        view["doctors"] = [{"name": d.user.full_name, "spec": d.specialization}
                           for d in accepted_doctors_for_patient(patient.id)]
    return render_template("family_dashboard.html", fm=fm, links=links, view=view, perm=perm)


@bp.route("/health")
@role_required(ROLE_FAMILY)
def health():
    fm, links = _link()
    if not fm:
        return redirect(url_for("family.dashboard"))
    patient, perm = fm.patient, fm.permission
    twin = compute_twin(patient)
    view = {"patient_name": patient.full_name}
    if perm.view_health_score and twin:
        view["scores"] = twin["scores"]
    if perm.view_history and twin:
        p = twin["profile"]
        view["history"] = {
            "conditions": [n for n, f in [("Diabetes", p.hist_diabetes), ("Hypertension", p.hist_hypertension),
                                          ("Heart disease", p.hist_heart_disease), ("Kidney disease", p.hist_kidney_disease),
                                          ("Asthma", p.hist_asthma), ("Thyroid disorder", p.hist_thyroid)] if f],
            "allergies": p.allergies, "medications": p.current_medications,
            "family": [n for n, f in [("Diabetes", p.fam_diabetes), ("Heart disease", p.fam_heart_disease),
                                      ("Stroke", p.fam_stroke), ("Cancer", p.fam_cancer),
                                      ("Kidney disease", p.fam_kidney_disease)] if f],
        }
    if perm.view_labs and twin and twin["labs"]:
        l = twin["labs"]
        view["labs"] = {"HbA1c": l.hba1c, "Fasting blood sugar": l.fasting_blood_sugar,
                        "Total cholesterol": l.total_cholesterol, "Hemoglobin": l.hemoglobin,
                        "Creatinine": l.creatinine, "ALT": l.liver_alt, "eGFR": l.kidney_egfr,
                        "_when": l.recorded_at}
    if perm.view_symptoms and twin:
        view["symptoms"] = twin["symptoms_list"]
        view["symptoms_when"] = twin["symptom_log"].recorded_at if twin["symptom_log"] else None
    return render_template("family_health.html", fm=fm, links=links, view=view, perm=perm)


@bp.route("/vitals")
@role_required(ROLE_FAMILY)
def vitals():
    fm, links = _link()
    if not fm:
        return redirect(url_for("family.dashboard"))
    family_require(fm, "view_vitals")
    patient = fm.patient
    rows = patient.vitals[-30:]
    data = [{"t": v.recorded_at.strftime("%d %b %H:%M"), "sys": v.systolic_bp, "dia": v.diastolic_bp,
             "hr": v.heart_rate, "spo2": v.oxygen_saturation} for v in rows]
    return render_template("family_vitals.html", fm=fm, links=links, latest=(rows[-1] if rows else None),
                           data=data, patient_name=patient.full_name)


@bp.route("/updates")
@role_required(ROLE_FAMILY)
def updates():
    fm, links = _link()
    if not fm:
        return redirect(url_for("family.dashboard"))
    kinds = _allowed_timeline_kinds(fm)
    events = build_timeline(fm.patient, allowed=kinds, limit=40) if kinds else []
    return render_template("family_updates.html", fm=fm, links=links, events=events,
                           patient_name=fm.patient.full_name)


@bp.route("/alerts")
@role_required(ROLE_FAMILY)
def alerts():
    fm, links = _link()
    if not fm:
        return redirect(url_for("family.dashboard"))
    family_require(fm, "emergency_alerts")
    events = (EmergencyEvent.query.filter_by(patient_id=fm.patient_id)
              .order_by(EmergencyEvent.created_at.desc()).limit(30).all())
    lv = fm.patient.vitals[-1] if fm.patient.vitals else None
    return render_template("family_alerts.html", fm=fm, links=links, events=events,
                           active=check_emergency(lv), patient_name=fm.patient.full_name)


@bp.route("/conversations")
@role_required(ROLE_FAMILY)
def conversations():
    """Read-only. Never marks messages read and offers no attachment download."""
    fm, links = _link()
    if not fm:
        return redirect(url_for("family.dashboard"))
    family_require(fm, "view_doctor_conversations")
    # only conversations with doctors who are CURRENTLY connected to the patient
    active_doctor_ids = {d.id for d in accepted_doctors_for_patient(fm.patient_id)}
    convs = [c for c in Conversation.query.filter_by(patient_id=fm.patient_id).all()
             if c.doctor_id in active_doctor_ids]
    return render_template("family_conversations.html", fm=fm, links=links, convs=convs,
                           patient_name=fm.patient.full_name)
