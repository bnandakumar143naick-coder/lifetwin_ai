"""
Digital Health Twin service.

This does NOT contain any health calculation. It calls the SAME engines in
utils/ that the original patient dashboard uses (compute_all_scores,
predict_all_risks, analyze_symptoms, generate_*, check_emergency) — it only
lets them run for a chosen user instead of `current_user`, and it never writes
to the database (the original dashboard writes a score snapshot; doctor/family
views must not).
"""
from utils.health_score import compute_all_scores
from utils.risk_predictor import predict_all_risks
from utils.symptom_analyzer import analyze_symptoms
from utils.emergency import check_emergency
from utils.plan_generator import (
    generate_diet_plan, generate_exercise_plan, generate_lifestyle_plan, generate_preventive_care,
)


def latest_bundle(user):
    profile = user.profile
    vitals = user.vitals[-1] if user.vitals else None
    labs = user.labs[-1] if user.labs else None
    symptom_log = user.symptom_logs[-1] if user.symptom_logs else None
    return profile, vitals, labs, symptom_log


def compute_twin(user):
    """Same result shape as app.compute_everything(), for an arbitrary user."""
    profile, vitals, labs, symptom_log = latest_bundle(user)
    if not profile:
        return None
    scores = compute_all_scores(profile, vitals, labs)
    risks = predict_all_risks(user, profile, vitals, labs)
    symptoms_list = symptom_log.symptoms.split(",") if symptom_log and symptom_log.symptoms else []
    symptom_result = analyze_symptoms([s for s in symptoms_list if s], profile)
    return {
        "profile": profile, "vitals": vitals, "labs": labs,
        "symptom_log": symptom_log, "symptoms_list": [s for s in symptoms_list if s],
        "scores": scores, "risks": risks, "symptom_result": symptom_result,
        "diet_plan": generate_diet_plan(profile, risks),
        "exercise_plan": generate_exercise_plan(profile, risks),
        "lifestyle_plan": generate_lifestyle_plan(profile, scores),
        "preventive_care": generate_preventive_care(risks, user.age),
        "emergency_alerts": check_emergency(vitals),
    }


def status_label(score, has_emergency):
    """Triage-style label derived from the EXISTING health score (a display
    heuristic for sorting/attention, not a diagnosis)."""
    if has_emergency:
        return "Emergency", "high"
    if score is None:
        return "No data", "medium"
    if score >= 75:
        return "Stable", "low"
    if score >= 60:
        return "Attention", "medium"
    return "High Risk", "high"


def patient_summary(user):
    twin = compute_twin(user)
    if not twin:
        label, css = status_label(None, False)
        return {"user": user, "score": None, "label": label, "css": css, "twin": None,
                "emergency": [], "last_update": _last_update(user)}
    score = twin["scores"]["overall"]
    label, css = status_label(score, bool(twin["emergency_alerts"]))
    return {"user": user, "score": score, "label": label, "css": css, "twin": twin,
            "emergency": twin["emergency_alerts"], "last_update": _last_update(user)}


def _last_update(user):
    stamps = []
    if user.vitals:
        stamps.append(user.vitals[-1].recorded_at)
    if user.labs:
        stamps.append(user.labs[-1].recorded_at)
    if user.symptom_logs:
        stamps.append(user.symptom_logs[-1].recorded_at)
    if user.profile and user.profile.updated_at:
        stamps.append(user.profile.updated_at)
    stamps = [s for s in stamps if s]
    return max(stamps) if stamps else None
