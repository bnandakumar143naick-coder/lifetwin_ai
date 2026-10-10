"""Chronological health timeline, built only from records that already exist."""
from models_ecosystem import (
    DoctorPatientConnection, EmergencyEvent, CONN_ACCEPTED,
)


def _fmt_bp(v):
    return f"{v.systolic_bp or '-'}/{v.diastolic_bp or '-'}"


def build_timeline(user, allowed=None, limit=60):
    """allowed: set of event kinds to include (None = everything).
    kinds: vitals, labs, symptoms, score, connection, emergency"""
    def ok(kind):
        return allowed is None or kind in allowed

    events = []

    if ok("vitals"):
        for v in user.vitals:
            parts = []
            if v.systolic_bp or v.diastolic_bp:
                parts.append(f"BP {_fmt_bp(v)}")
            if v.heart_rate:
                parts.append(f"HR {v.heart_rate}")
            if v.oxygen_saturation:
                parts.append(f"SpO2 {v.oxygen_saturation}%")
            if v.blood_sugar:
                parts.append(f"Sugar {v.blood_sugar}")
            events.append({"kind": "vitals", "when": v.recorded_at, "icon": "❤️",
                           "title": "New vitals recorded", "detail": " · ".join(parts) or "—"})

    if ok("labs"):
        for l in user.labs:
            parts = []
            if l.hba1c is not None:
                parts.append(f"HbA1c {l.hba1c}")
            if l.total_cholesterol is not None:
                parts.append(f"Cholesterol {l.total_cholesterol}")
            if l.creatinine is not None:
                parts.append(f"Creatinine {l.creatinine}")
            if l.kidney_egfr is not None:
                parts.append(f"eGFR {l.kidney_egfr}")
            title = "Lab report uploaded" if l.file_path else "Lab values recorded"
            events.append({"kind": "labs", "when": l.recorded_at, "icon": "🧪",
                           "title": title, "detail": " · ".join(parts) or "—"})

    if ok("symptoms"):
        for s in user.symptom_logs:
            events.append({"kind": "symptoms", "when": s.recorded_at, "icon": "🩹",
                           "title": "Symptoms recorded",
                           "detail": (s.symptoms or "").replace(",", ", ") or "None selected"})

    if ok("score"):
        prev = None
        for h in user.score_history:  # only show when the score actually changed
            if h.overall_score != prev:
                events.append({"kind": "score", "when": h.recorded_at, "icon": "📊",
                               "title": "Health score", "detail": f"{h.overall_score}/100"})
                prev = h.overall_score

    if ok("connection"):
        rows = DoctorPatientConnection.query.filter_by(patient_id=user.id, status=CONN_ACCEPTED).all()
        for c in rows:
            if c.accepted_at:
                events.append({"kind": "connection", "when": c.accepted_at, "icon": "🤝",
                               "title": "Doctor connection accepted",
                               "detail": f"Dr. {c.doctor.user.full_name}"})

    if ok("emergency"):
        for e in EmergencyEvent.query.filter_by(patient_id=user.id).all():
            events.append({"kind": "emergency", "when": e.created_at, "icon": "🚨",
                           "title": "Emergency threshold detected", "detail": "; ".join(e.lines)})

    events = [e for e in events if e["when"]]
    events.sort(key=lambda e: e["when"], reverse=True)
    return events[:limit]
