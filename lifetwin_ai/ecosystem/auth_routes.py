"""Doctor registration/login and family login (patients keep the original /login, /register)."""
import re

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, current_user
from sqlalchemy.exc import IntegrityError

from models import db, User
from models_ecosystem import (
    Doctor, ROLE_DOCTOR, ROLE_FAMILY, VERIFY_PENDING, VERIFY_VERIFIED,
)
from ecosystem.security import role_home_url, safe_next_url

bp = Blueprint("eco_auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8


def _clean(name, maxlen):
    return (request.form.get(name, "") or "").strip()[:maxlen]


@bp.route("/doctor/register", methods=["GET", "POST"])
def doctor_register():
    if current_user.is_authenticated and request.method == "GET":
        return redirect(role_home_url(current_user))
    if request.method == "POST":
        f = {
            "full_name": _clean("full_name", 120), "email": _clean("email", 120).lower(),
            "phone": _clean("phone", 30), "specialization": _clean("specialization", 120),
            "qualification": _clean("qualification", 200), "hospital": _clean("hospital", 200),
            "license_number": _clean("license_number", 80),
        }
        password = request.form.get("password", "")
        exp = request.form.get("experience_years", type=int)

        required = ["full_name", "email", "phone", "specialization", "qualification", "hospital", "license_number"]
        if not all(f[k] for k in required) or not password or exp is None:
            flash("Please fill in all fields.", "error")
            return render_template("doctor_register.html", f=f, exp=exp)
        if not EMAIL_RE.match(f["email"]):
            flash("Please enter a valid email address.", "error")
            return render_template("doctor_register.html", f=f, exp=exp)
        if len(password) < MIN_PASSWORD:
            flash(f"Password must be at least {MIN_PASSWORD} characters.", "error")
            return render_template("doctor_register.html", f=f, exp=exp)
        if exp < 0 or exp > 70:
            flash("Years of experience must be between 0 and 70.", "error")
            return render_template("doctor_register.html", f=f, exp=exp)

        if User.query.filter_by(email=f["email"]).first():
            flash("An account with this email already exists.", "error")
            return render_template("doctor_register.html", f=f, exp=exp)
        if Doctor.query.filter(db.func.lower(Doctor.license_number) == f["license_number"].lower()).first():
            flash("A doctor account with this registration/licence number already exists.", "error")
            return render_template("doctor_register.html", f=f, exp=exp)

        try:
            # age/gender are NOT NULL in the original users table; doctors get neutral placeholders.
            user = User(full_name=f["full_name"], email=f["email"], age=0, gender="N/A",
                        role=ROLE_DOCTOR, phone=f["phone"])
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            auto = current_app.config.get("AUTO_VERIFY_DOCTORS", False)
            doctor = Doctor(user_id=user.id, specialization=f["specialization"],
                            qualification=f["qualification"], hospital=f["hospital"],
                            experience_years=exp, license_number=f["license_number"],
                            verification_status=VERIFY_VERIFIED if auto else VERIFY_PENDING)
            db.session.add(doctor)
            db.session.flush()
            doctor.doctor_code = f"DR-{doctor.id:06d}"
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("A doctor account with these details already exists.", "error")
            return render_template("doctor_register.html", f=f, exp=exp)

        login_user(user)
        if auto:
            flash("Doctor account created (auto-verified in this configuration).", "success")
        else:
            flash("Doctor account created. Your profile is PENDING verification; you will appear in "
                  "patient search once an administrator verifies it.", "info")
        return redirect(url_for("doctor.dashboard"))
    return render_template("doctor_register.html", f={}, exp=None)


def _portal_login(role, template, home_endpoint):
    if current_user.is_authenticated and request.method == "GET":
        return redirect(role_home_url(current_user))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if user.role != role:
                flash("This account is not registered for this portal. Please use the correct login page.", "error")
                return render_template(template)
            login_user(user)
            return redirect(safe_next_url(url_for(home_endpoint)))
        flash("Invalid email or password.", "error")
    return render_template(template)


@bp.route("/doctor/login", methods=["GET", "POST"])
def doctor_login():
    return _portal_login(ROLE_DOCTOR, "doctor_login.html", "doctor.dashboard")


@bp.route("/family/login", methods=["GET", "POST"])
def family_login():
    return _portal_login(ROLE_FAMILY, "family_login.html", "family.dashboard")
