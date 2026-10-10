"""Doctor portal. Every patient-data route goes through authorize_doctor_for_patient()."""
import os
from datetime import datetime, timedelta

from flask import (Blueprint, render_template, request, redirect, url_for, flash, abort,
                   send_file, send_from_directory, current_app)
from flask_login import current_user

from models import db, User, LabReport, VitalSigns
from models_ecosystem import (
    Doctor, DoctorPatientConnection, Conversation, Message, Notification, EmergencyEvent,
    ProfileWeightLog, ROLE_DOCTOR, CONN_PENDING, CONN_ACCEPTED, CONN_REJECTED, CONN_BLOCKED,
    N_CONNECTION, N_EMERGENCY,
)
from config import Config
from ecosystem.security import role_required
from ecosystem.access import (
    current_doctor_or_403, authorize_doctor_for_patient, accepted_patient_ids,
    get_or_create_conversation, authorize_conversation_participant,
)
from ecosystem.twin import patient_summary, compute_twin
from ecosystem.timeline import build_timeline
from ecosystem.notify import notify
from ecosystem import chat
from utils.pdf_report import generate_pdf_report

bp = Blueprint("doctor", __name__, url_prefix="/doctor")


def _patients(doctor):
    ids = accepted_patient_ids(doctor)
    users = User.query.filter(User.id.in_(ids)).all() if ids else []
    return [patient_summary(u) for u in users]


def _sorted_by_attention(summaries):
    rank = {"Emergency": 0, "High Risk": 1, "Attention": 2, "No data": 3, "Stable": 4}
    return sorted(summaries, key=lambda s: (rank.get(s["label"], 5), s["user"].full_name.lower()))


# ---------------- dashboard ----------------
@bp.route("/dashboard")
@role_required(ROLE_DOCTOR)
def dashboard():
    doctor = current_doctor_or_403()
    summaries = _sorted_by_attention(_patients(doctor)) if doctor.is_verified else []
    pending = DoctorPatientConnection.query.filter_by(doctor_id=doctor.id, status=CONN_PENDING).count()
    unread_msgs = (db.session.query(Message).join(Conversation, Message.conversation_id == Conversation.id)
                   .filter(Conversation.doctor_id == doctor.id, Message.sender_user_id != current_user.id,
                           Message.is_read == False).count())  # noqa: E712
    emergencies = Notification.query.filter_by(user_id=current_user.id, notification_type=N_EMERGENCY,
                                               is_read=False).count()
    return render_template("doctor_dashboard.html", doctor=doctor, summaries=summaries,
                           stats={"patients": len(summaries), "pending": pending,
                                  "unread": unread_msgs, "emergency": emergencies})


# ---------------- patients & requests ----------------
@bp.route("/patients")
@role_required(ROLE_DOCTOR)
def patients():
    doctor = current_doctor_or_403()
    summaries = _sorted_by_attention(_patients(doctor)) if doctor.is_verified else []
    return render_template("doctor_patients.html", doctor=doctor, summaries=summaries)


@bp.route("/requests")
@role_required(ROLE_DOCTOR)
def requests_page():
    doctor = current_doctor_or_403()
    pending = (DoctorPatientConnection.query.filter_by(doctor_id=doctor.id, status=CONN_PENDING)
               .order_by(DoctorPatientConnection.requested_at.desc()).all())
    history = (DoctorPatientConnection.query
               .filter(DoctorPatientConnection.doctor_id == doctor.id,
                       DoctorPatientConnection.status.in_([CONN_REJECTED, CONN_BLOCKED]))
               .order_by(DoctorPatientConnection.responded_at.desc()).limit(20).all())
    return render_template("doctor_requests.html", doctor=doctor, pending=pending, history=history)


@bp.route("/requests/<int:cid>/<action>", methods=["POST"])
@role_required(ROLE_DOCTOR)
def request_action(cid, action):
    doctor = current_doctor_or_403()
    conn = db.session.get(DoctorPatientConnection, cid)
    if not conn or conn.doctor_id != doctor.id:
        abort(403)
    if action not in ("accept", "reject", "block", "disconnect"):
        abort(400, description="Unknown action.")
    if not doctor.is_verified and action == "accept":
        flash("Your account must be verified before you can accept patients.", "error")
        return redirect(url_for("doctor.requests_page"))

    now = datetime.utcnow()
    name = current_user.full_name
    if action == "accept":
        if conn.status != CONN_PENDING:
            flash("This request is no longer pending.", "error")
            return redirect(url_for("doctor.requests_page"))
        conn.status, conn.responded_at, conn.accepted_at = CONN_ACCEPTED, now, now
        get_or_create_conversation(doctor.id, conn.patient_id)
        notify(conn.patient_id, N_CONNECTION, f"Dr. {name} accepted your connection request. You can now message your doctor.",
               link=f"/messages/{doctor.id}")
        flash(f"You are now connected with {conn.patient.full_name}.", "success")
    elif action == "reject":
        if conn.status != CONN_PENDING:
            flash("This request is no longer pending.", "error")
            return redirect(url_for("doctor.requests_page"))
        conn.status, conn.responded_at = CONN_REJECTED, now
        notify(conn.patient_id, N_CONNECTION, f"Dr. {name} declined your connection request.", link="/doctors")
        flash("Request rejected.", "info")
    elif action == "block":
        if conn.status == CONN_BLOCKED:
            flash("Already blocked.", "info")
            return redirect(url_for("doctor.requests_page"))
        conn.status, conn.responded_at = CONN_BLOCKED, now
        flash("Patient blocked. They can no longer request a connection.", "info")
    elif action == "disconnect":
        if conn.status != CONN_ACCEPTED:
            abort(400, description="Only connected patients can be disconnected.")
        conn.status, conn.responded_at = CONN_REJECTED, now
        notify(conn.patient_id, N_CONNECTION, f"Dr. {name} ended the connection.", link="/doctors")
        flash("Connection ended. Access to this patient's data has been removed.", "info")
    db.session.commit()
    return redirect(url_for("doctor.requests_page") if action != "disconnect" else url_for("doctor.patients"))


# ---------------- patient health data (authorized) ----------------
@bp.route("/patient/<int:pid>")
@role_required(ROLE_DOCTOR)
def patient_overview(pid):
    doctor, patient = authorize_doctor_for_patient(pid)
    twin = compute_twin(patient)  # existing engines; read-only
    return render_template("doctor_patient_overview.html", patient=patient, twin=twin, tab="overview")


@bp.route("/patient/<int:pid>/history")
@role_required(ROLE_DOCTOR)
def patient_history(pid):
    doctor, patient = authorize_doctor_for_patient(pid)
    vitals = patient.vitals[-60:]
    weight = ProfileWeightLog.query.filter_by(user_id=pid).order_by(ProfileWeightLog.id).all()
    weight_pts = [{"t": w.recorded_at.strftime("%d %b %Y"), "v": w.weight_kg} for w in weight]
    weight_note = None
    if not weight_pts and patient.profile and patient.profile.weight_kg:
        weight_pts = [{"t": "Current", "v": patient.profile.weight_kg}]
        weight_note = "Only the current weight is on file; the trend builds up each time the patient updates their profile."
    data = {
        "vitals": [{"t": v.recorded_at.strftime("%d %b %H:%M"), "sys": v.systolic_bp, "dia": v.diastolic_bp,
                    "hr": v.heart_rate, "spo2": v.oxygen_saturation, "sugar": v.blood_sugar} for v in vitals],
        "weight": weight_pts,
        "score": [{"t": h.recorded_at.strftime("%d %b %H:%M"), "v": h.overall_score} for h in patient.score_history[-60:]],
    }
    return render_template("doctor_patient_history.html", patient=patient, data=data,
                           weight_note=weight_note, tab="history")


@bp.route("/patient/<int:pid>/timeline")
@role_required(ROLE_DOCTOR)
def patient_timeline(pid):
    doctor, patient = authorize_doctor_for_patient(pid)
    labs_with_files = [l for l in patient.labs if l.file_path]
    return render_template("doctor_patient_timeline.html", patient=patient, events=build_timeline(patient),
                           labs_with_files=labs_with_files, tab="timeline")


@bp.route("/patient/<int:pid>/lab/<int:lab_id>/file")
@role_required(ROLE_DOCTOR)
def patient_lab_file(pid, lab_id):
    doctor, patient = authorize_doctor_for_patient(pid)
    lab = db.session.get(LabReport, lab_id)
    if not lab or lab.user_id != patient.id or not lab.file_path:
        abort(403)
    uploads = os.path.join(current_app.root_path, "instance", "uploads")
    if os.path.basename(lab.file_path) != lab.file_path:
        abort(403)
    return send_from_directory(uploads, lab.file_path, as_attachment=True)


@bp.route("/patient/<int:pid>/report")
@role_required(ROLE_DOCTOR)
def patient_report(pid):
    """Reuses the EXISTING PDF report generator for a connected patient."""
    doctor, patient = authorize_doctor_for_patient(pid)
    twin = compute_twin(patient)
    if not twin:
        flash("This patient has not completed a health profile yet.", "info")
        return redirect(url_for("doctor.patient_overview", pid=pid))
    fname = f"LifeTwin_Report_{patient.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf"
    fpath = os.path.join(Config.REPORTS_DIR, fname)
    generate_pdf_report(fpath, patient, twin["profile"], twin["vitals"], twin["symptom_result"],
                        twin["scores"], twin["risks"], twin["diet_plan"], twin["exercise_plan"],
                        twin["preventive_care"])
    return send_file(fpath, as_attachment=True, download_name=f"LifeTwin_Report_{patient.full_name.replace(' ', '_')}.pdf")


# ---------------- records / alerts ----------------
@bp.route("/records")
@role_required(ROLE_DOCTOR)
def records():
    doctor = current_doctor_or_403()
    rows = []
    if doctor.is_verified:
        for s in _patients(doctor):
            u = s["user"]
            rows.append({"user": u,
                         "vitals": u.vitals[-1].recorded_at if u.vitals else None,
                         "labs": u.labs[-1].recorded_at if u.labs else None,
                         "symptoms": u.symptom_logs[-1].recorded_at if u.symptom_logs else None,
                         "files": sum(1 for l in u.labs if l.file_path)})
    return render_template("doctor_records.html", doctor=doctor, rows=rows)


@bp.route("/alerts")
@role_required(ROLE_DOCTOR)
def alerts():
    doctor = current_doctor_or_403()
    events = []
    if doctor.is_verified:
        ids = accepted_patient_ids(doctor)
        if ids:
            since = datetime.utcnow() - timedelta(days=30)
            events = (EmergencyEvent.query.filter(EmergencyEvent.patient_id.in_(ids),
                                                  EmergencyEvent.created_at >= since)
                      .order_by(EmergencyEvent.created_at.desc()).all())
    # visiting the alert page acknowledges the doctor's emergency notifications
    Notification.query.filter_by(user_id=current_user.id, notification_type=N_EMERGENCY,
                                 is_read=False).update({"is_read": True})
    db.session.commit()
    return render_template("doctor_alerts.html", doctor=doctor, events=events)


# ---------------- messages ----------------
@bp.route("/messages")
@role_required(ROLE_DOCTOR)
def messages_index():
    doctor = current_doctor_or_403()
    rows = []
    if doctor.is_verified:
        for pid in accepted_patient_ids(doctor):
            conv = Conversation.query.filter_by(doctor_id=doctor.id, patient_id=pid).first()
            patient = db.session.get(User, pid)
            last = conv.messages[-1] if conv and conv.messages else None
            unread = sum(1 for m in (conv.messages if conv else [])
                         if m.sender_user_id != current_user.id and not m.is_read)
            rows.append({"name": patient.full_name, "subtitle": f"Age {patient.age}", "last": last,
                         "unread": unread, "url": url_for("doctor.thread", pid=pid)})
    rows.sort(key=lambda r: (r["last"].created_at if r["last"] else datetime.min), reverse=True)
    return render_template("messages_index.html", rows=rows, portal="doctor",
                           empty_text="No connected patients yet. Accept a connection request to start a conversation.")


@bp.route("/messages/<int:pid>", methods=["GET", "POST"])
@role_required(ROLE_DOCTOR)
def thread(pid):
    doctor, patient = authorize_doctor_for_patient(pid)
    conv = get_or_create_conversation(doctor.id, pid)
    db.session.commit()
    authorize_conversation_participant(conv)
    if request.method == "POST":
        chat.send_from_request(conv, pid, f"/messages/{doctor.id}", f"Dr. {current_user.full_name}")
        return redirect(url_for("doctor.thread", pid=pid))
    return chat.render_thread(conv, patient.full_name, f"Patient · Age {patient.age}",
                              url_for("doctor.thread", pid=pid), url_for("doctor.messages_index"))


# ---------------- profile ----------------
@bp.route("/profile", methods=["GET", "POST"])
@role_required(ROLE_DOCTOR)
def profile():
    doctor = current_doctor_or_403()
    if request.method == "POST":
        spec = request.form.get("specialization", "").strip()[:120]
        qual = request.form.get("qualification", "").strip()[:200]
        hosp = request.form.get("hospital", "").strip()[:200]
        exp = request.form.get("experience_years", type=int)
        bio = request.form.get("bio", "").strip()[:1000]
        if not (spec and qual and hosp) or exp is None or exp < 0 or exp > 70:
            flash("Please provide valid specialization, qualification, hospital and experience.", "error")
            return redirect(url_for("doctor.profile"))
        doctor.specialization, doctor.qualification, doctor.hospital = spec, qual, hosp
        doctor.experience_years, doctor.bio = exp, (bio or None)
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("doctor.profile"))
    return render_template("doctor_profile.html", doctor=doctor)
