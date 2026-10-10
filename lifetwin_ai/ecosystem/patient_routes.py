"""New PATIENT features: find doctor, connections, messages, family, emergency, own lab files.
The original patient routes (dashboard, profile, vitals, ...) remain in app.py, unchanged."""
import os
import re
from datetime import datetime

from flask import (Blueprint, render_template, request, redirect, url_for, flash, abort,
                   current_app, send_from_directory)
from flask_login import current_user

from models import db, User, LabReport
from models_ecosystem import (
    Doctor, DoctorPatientConnection, Conversation, FamilyMember, FamilyPermission, EmergencyEvent,
    ROLE_PATIENT, ROLE_FAMILY, CONN_PENDING, CONN_ACCEPTED, CONN_REJECTED, CONN_BLOCKED,
    FAMILY_PERMISSION_FIELDS, FAMILY_PERMISSION_KEYS, N_CONNECTION, N_FAMILY_ACCESS,
    VERIFY_VERIFIED,
)
from ecosystem.security import role_required
from ecosystem.access import (
    get_connection, get_or_create_conversation, authorize_conversation_participant,
    accepted_doctors_for_patient,
)
from ecosystem.notify import notify
from ecosystem import chat
from utils.emergency import check_emergency

bp = Blueprint("pt", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DEFAULT_ON = {"emergency_alerts", "view_vitals", "view_health_score"}  # pre-checked in the "add" form only


# ======================= find doctor / profile / connection =======================
def _like_escape(q):
    return q.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


@bp.route("/doctors")
@role_required(ROLE_PATIENT)
def doctors():
    q = request.args.get("q", "").strip()[:80]
    query = Doctor.query.join(User, User.id == Doctor.user_id).filter(Doctor.verification_status == VERIFY_VERIFIED)
    if q:
        like = f"%{_like_escape(q)}%"
        query = query.filter(db.or_(
            User.full_name.ilike(like, escape="\\"), Doctor.doctor_code.ilike(like, escape="\\"),
            Doctor.specialization.ilike(like, escape="\\"), Doctor.hospital.ilike(like, escape="\\"),
        ))
    results = query.order_by(User.full_name).limit(50).all()
    conns = {c.doctor_id: c for c in DoctorPatientConnection.query.filter_by(patient_id=current_user.id).all()}
    mine = [c for c in conns.values() if c.status in (CONN_PENDING, CONN_ACCEPTED)]
    return render_template("doctors_search.html", q=q, results=results, conns=conns, mine=mine)


@bp.route("/doctors/<int:doctor_id>")
@role_required(ROLE_PATIENT)
def doctor_profile(doctor_id):
    doctor = db.session.get(Doctor, doctor_id)
    if not doctor or not doctor.is_verified:
        abort(404)
    conn = get_connection(doctor.id, current_user.id)
    return render_template("doctor_public_profile.html", doctor=doctor, conn=conn)


@bp.route("/doctors/<int:doctor_id>/request", methods=["POST"])
@role_required(ROLE_PATIENT)
def request_connection(doctor_id):
    doctor = db.session.get(Doctor, doctor_id)
    if not doctor or not doctor.is_verified:
        flash("That doctor could not be found.", "error")
        return redirect(url_for("pt.doctors"))
    conn = get_connection(doctor.id, current_user.id)
    if conn:
        if conn.status == CONN_PENDING:
            flash("You already have a pending request with this doctor.", "info")
            return redirect(url_for("pt.doctor_profile", doctor_id=doctor.id))
        if conn.status == CONN_ACCEPTED:
            flash("You are already connected with this doctor.", "info")
            return redirect(url_for("pt.doctor_profile", doctor_id=doctor.id))
        if conn.status == CONN_BLOCKED:
            flash("You cannot send a request to this doctor.", "error")
            return redirect(url_for("pt.doctors"))
        conn.status, conn.requested_at, conn.responded_at, conn.accepted_at = CONN_PENDING, datetime.utcnow(), None, None
    else:
        conn = DoctorPatientConnection(doctor_id=doctor.id, patient_id=current_user.id, status=CONN_PENDING)
        db.session.add(conn)
    notify(doctor.user_id, N_CONNECTION,
           f"New patient connection request from {current_user.full_name} (age {current_user.age}).",
           link="/doctor/requests")
    db.session.commit()
    flash(f"Connection request sent to Dr. {doctor.user.full_name}.", "success")
    return redirect(url_for("pt.doctor_profile", doctor_id=doctor.id))


@bp.route("/connections/<int:cid>/remove", methods=["POST"])
@role_required(ROLE_PATIENT)
def remove_connection(cid):
    conn = db.session.get(DoctorPatientConnection, cid)
    if not conn or conn.patient_id != current_user.id:
        abort(403)
    if conn.status not in (CONN_PENDING, CONN_ACCEPTED):
        flash("Nothing to remove.", "info")
        return redirect(url_for("pt.doctors"))
    was = conn.status
    conn.status, conn.responded_at = CONN_REJECTED, datetime.utcnow()
    notify(conn.doctor.user_id, N_CONNECTION,
           f"{current_user.full_name} {'cancelled their request' if was == CONN_PENDING else 'disconnected from you'}.",
           link="/doctor/patients")
    db.session.commit()
    flash("Connection removed. This doctor can no longer see your health data.", "success")
    return redirect(url_for("pt.doctors"))


# ======================= messages =======================
@bp.route("/messages")
@role_required(ROLE_PATIENT)
def messages_index():
    rows = []
    for d in accepted_doctors_for_patient(current_user.id):
        conv = Conversation.query.filter_by(doctor_id=d.id, patient_id=current_user.id).first()
        last = conv.messages[-1] if conv and conv.messages else None
        unread = sum(1 for m in (conv.messages if conv else [])
                     if m.sender_user_id != current_user.id and not m.is_read)
        rows.append({"name": f"Dr. {d.user.full_name}", "subtitle": d.specialization, "last": last,
                     "unread": unread, "url": url_for("pt.thread", doctor_id=d.id)})
    rows.sort(key=lambda r: (r["last"].created_at if r["last"] else datetime.min), reverse=True)
    return render_template("messages_index.html", rows=rows, portal="patient",
                           empty_text="No connected doctors yet. Find a doctor and send a connection request.")


@bp.route("/messages/<int:doctor_id>", methods=["GET", "POST"])
@role_required(ROLE_PATIENT)
def thread(doctor_id):
    doctor = db.session.get(Doctor, doctor_id)
    conn = get_connection(doctor_id, current_user.id) if doctor else None
    if not doctor or not conn or conn.status != CONN_ACCEPTED or not doctor.is_verified:
        abort(403)
    conv = get_or_create_conversation(doctor.id, current_user.id)
    db.session.commit()
    authorize_conversation_participant(conv)
    if request.method == "POST":
        chat.send_from_request(conv, doctor.user_id, "/doctor/messages/%d" % current_user.id, current_user.full_name)
        return redirect(url_for("pt.thread", doctor_id=doctor.id))
    return chat.render_thread(conv, f"Dr. {doctor.user.full_name}", f"{doctor.specialization} · {doctor.hospital}",
                              url_for("pt.thread", doctor_id=doctor.id), url_for("pt.messages_index"))


# ======================= own lab file download (the original app had none) =======================
@bp.route("/files/lab/<int:lab_id>")
@role_required(ROLE_PATIENT)
def lab_file(lab_id):
    lab = db.session.get(LabReport, lab_id)
    if not lab or lab.user_id != current_user.id or not lab.file_path:
        abort(403)
    if os.path.basename(lab.file_path) != lab.file_path:
        abort(403)
    return send_from_directory(os.path.join(current_app.root_path, "instance", "uploads"),
                               lab.file_path, as_attachment=True)


# ======================= family management =======================
def _own_link_or_403(fm_id):
    fm = db.session.get(FamilyMember, fm_id)
    if not fm or fm.patient_id != current_user.id:
        abort(403)
    return fm


def _perm_from_form():
    return {k: bool(request.form.get(k)) for k in FAMILY_PERMISSION_KEYS}


@bp.route("/my-family")
@role_required(ROLE_PATIENT)
def family_manage():
    links = FamilyMember.query.filter_by(patient_id=current_user.id).order_by(FamilyMember.id).all()
    return render_template("family_manage.html", links=links, fields=FAMILY_PERMISSION_FIELDS,
                           default_on=DEFAULT_ON)


@bp.route("/my-family/add", methods=["POST"])
@role_required(ROLE_PATIENT)
def family_add():
    name = request.form.get("full_name", "").strip()[:120]
    email = request.form.get("email", "").strip().lower()[:120]
    phone = request.form.get("phone", "").strip()[:30]
    relation = request.form.get("relationship", "").strip()[:50]
    password = request.form.get("password", "")

    if not name or not email or not relation:
        flash("Name, email and relationship are required.", "error")
        return redirect(url_for("pt.family_manage"))
    if not EMAIL_RE.match(email):
        flash("Please enter a valid email address.", "error")
        return redirect(url_for("pt.family_manage"))

    member = User.query.filter_by(email=email).first()
    if member:
        if member.role != ROLE_FAMILY:
            flash("That email belongs to a different kind of account and cannot be used as a family login.", "error")
            return redirect(url_for("pt.family_manage"))
        if FamilyMember.query.filter_by(patient_id=current_user.id, user_id=member.id).first():
            flash("This family member is already added.", "error")
            return redirect(url_for("pt.family_manage"))
    else:
        if len(password) < 8:
            flash("Set an initial password of at least 8 characters for the new family login "
                  "(share it with them privately; they can change it in Profile).", "error")
            return redirect(url_for("pt.family_manage"))
        member = User(full_name=name, email=email, age=0, gender="N/A", role=ROLE_FAMILY, phone=phone or None)
        member.set_password(password)
        db.session.add(member)
        db.session.flush()

    link = FamilyMember(patient_id=current_user.id, user_id=member.id, relationship_label=relation)
    link.permission = FamilyPermission(**_perm_from_form())
    db.session.add(link)
    db.session.flush()
    notify(member.id, N_FAMILY_ACCESS,
           f"{current_user.full_name} added you as a family member ({relation}). "
           f"Open your Family dashboard to see what has been shared with you.", link=f"/family/dashboard?fm={link.id}")
    notify(current_user.id, N_FAMILY_ACCESS, f"Family access granted to {member.full_name} ({relation}).", link="/my-family")
    db.session.commit()
    flash(f"{member.full_name} added as {relation}.", "success")
    return redirect(url_for("pt.family_manage"))


@bp.route("/my-family/<int:fm_id>/permissions", methods=["POST"])
@role_required(ROLE_PATIENT)
def family_permissions(fm_id):
    link = _own_link_or_403(fm_id)
    values = _perm_from_form()
    for k, v in values.items():
        setattr(link.permission, k, v)
    notify(link.user_id, N_FAMILY_ACCESS, f"{current_user.full_name} updated what you can see.",
           link=f"/family/dashboard?fm={link.id}")
    notify(current_user.id, N_FAMILY_ACCESS, f"Family access changed for {link.member_user.full_name}.", link="/my-family")
    db.session.commit()
    flash("Permissions updated.", "success")
    return redirect(url_for("pt.family_manage"))


@bp.route("/my-family/<int:fm_id>/remove", methods=["POST"])
@role_required(ROLE_PATIENT)
def family_remove(fm_id):
    link = _own_link_or_403(fm_id)
    member_name, member_id = link.member_user.full_name, link.user_id
    db.session.delete(link)
    notify(member_id, N_FAMILY_ACCESS, f"{current_user.full_name} removed your access.", link="/family/dashboard")
    notify(current_user.id, N_FAMILY_ACCESS, f"Family access removed for {member_name}.", link="/my-family")
    db.session.commit()
    flash(f"{member_name}'s access has been removed.", "success")
    return redirect(url_for("pt.family_manage"))


# ======================= emergency =======================
@bp.route("/emergency")
@role_required(ROLE_PATIENT)
def emergency():
    latest = current_user.vitals[-1] if current_user.vitals else None
    current_alerts = check_emergency(latest)  # existing engine
    events = (EmergencyEvent.query.filter_by(patient_id=current_user.id)
              .order_by(EmergencyEvent.created_at.desc()).limit(20).all())
    doctors = accepted_doctors_for_patient(current_user.id)
    family = (FamilyMember.query.join(FamilyPermission, FamilyPermission.family_member_id == FamilyMember.id)
              .filter(FamilyMember.patient_id == current_user.id, FamilyPermission.emergency_alerts == True)  # noqa: E712
              .all())
    return render_template("emergency.html", current_alerts=current_alerts, events=events,
                           doctors=doctors, family=family)
