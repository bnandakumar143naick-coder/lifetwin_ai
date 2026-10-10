
import os
from datetime import datetime

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, send_file
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)

from config import Config
from models import db, User, HealthProfile, VitalSigns, LabReport, SymptomLog, HealthScoreHistory
from utils.health_score import compute_all_scores
from utils.risk_predictor import predict_all_risks
from utils.symptom_analyzer import analyze_symptoms, SYMPTOM_MAP
from utils.emergency import check_emergency
from utils.plan_generator import (
    generate_diet_plan, generate_exercise_plan, generate_lifestyle_plan, generate_preventive_care
)
from utils.health_coach import answer_question
from utils.pdf_report import generate_pdf_report

# Patient + Doctor + Family ecosystem
import models_ecosystem  # noqa: F401
from ecosystem import (
    register_ecosystem, ensure_ecosystem_schema,
    after_vitals_saved, after_lab_saved, after_symptoms_saved, after_profile_saved,
)
from werkzeug.utils import secure_filename


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Vercel's application directory is read-only.
    # Configure writable paths here, even if config.py is an older version.
    if os.environ.get("VERCEL"):
        instance_dir = "/tmp/lifetwin_instance"
        os.makedirs(instance_dir, exist_ok=True)

        # SQLite in /tmp is temporary. Use DATABASE_URL for persistent storage.
        if not os.environ.get("DATABASE_URL"):
            app.config["SQLALCHEMY_DATABASE_URI"] = (
                "sqlite:///" + os.path.join(instance_dir, "lifetwin.db")
            )

        reports_dir = os.path.join(instance_dir, "reports")
    else:
        instance_dir = getattr(
            Config, "INSTANCE_DIR",
            os.path.join(app.root_path, "instance")
        )
        reports_dir = getattr(
            Config, "REPORTS_DIR",
            os.path.join(instance_dir, "reports")
        )

    app.config["INSTANCE_DIR"] = instance_dir
    app.config["REPORTS_DIR"] = reports_dir

    os.makedirs(instance_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.login_message = "Please log in to access LifeTwin AI."
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    with app.app_context():
        db.create_all()
        ensure_ecosystem_schema(db)

    # ---------- helper ----------

    def get_user_bundle():
        """Fetch profile + latest vitals + latest labs + latest symptoms."""
        profile = current_user.profile
        vitals = current_user.vitals[-1] if current_user.vitals else None
        labs = current_user.labs[-1] if current_user.labs else None
        symptom_log = current_user.symptom_logs[-1] if current_user.symptom_logs else None
        return profile, vitals, labs, symptom_log

    def compute_everything():
        profile, vitals, labs, symptom_log = get_user_bundle()
        if not profile:
            return None

        scores = compute_all_scores(profile, vitals, labs)
        risks = predict_all_risks(current_user, profile, vitals, labs)

        symptoms_list = (
            symptom_log.symptoms.split(",")
            if symptom_log and symptom_log.symptoms
            else []
        )
        symptom_result = analyze_symptoms(
            [s for s in symptoms_list if s], profile
        )

        diet_plan = generate_diet_plan(profile, risks)
        exercise_plan = generate_exercise_plan(profile, risks)
        lifestyle_plan = generate_lifestyle_plan(profile, scores)
        preventive_care = generate_preventive_care(risks, current_user.age)
        emergency_alerts = check_emergency(vitals)

        return {
            "profile": profile,
            "vitals": vitals,
            "labs": labs,
            "scores": scores,
            "risks": risks,
            "symptom_result": symptom_result,
            "diet_plan": diet_plan,
            "exercise_plan": exercise_plan,
            "lifestyle_plan": lifestyle_plan,
            "preventive_care": preventive_care,
            "emergency_alerts": emergency_alerts,
        }

    # ---------- public ----------

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template("index.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            age = request.form.get("age", type=int)
            gender = request.form.get("gender", "")

            if not all([full_name, email, password, age, gender]):
                flash("Please fill in all fields.", "error")
                return render_template("register.html")

            if User.query.filter_by(email=email).first():
                flash("An account with this email already exists.", "error")
                return render_template("register.html")

            user = User(
                full_name=full_name,
                email=email,
                age=age,
                gender=gender,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            login_user(user)
            flash("Account created! Let's set up your health profile.", "success")
            return redirect(url_for("edit_profile"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email).first()

            if user and user.check_password(password):
                login_user(user)
                return redirect(url_for("dashboard"))

            flash("Invalid email or password.", "error")

        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("index"))

    # ---------- profile ----------

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def edit_profile():
        profile = current_user.profile

        if request.method == "POST":
            if not profile:
                profile = HealthProfile(user_id=current_user.id)
                db.session.add(profile)

            profile.height_cm = request.form.get("height_cm", type=float)
            profile.weight_kg = request.form.get("weight_kg", type=float)
            profile.smoking = request.form.get("smoking")
            profile.alcohol = request.form.get("alcohol")
            profile.exercise_frequency = request.form.get("exercise_frequency")
            profile.sleep_hours = request.form.get("sleep_hours", type=float)
            profile.water_intake_l = request.form.get("water_intake_l", type=float)
            profile.stress_level = request.form.get("stress_level")
            profile.occupation = request.form.get("occupation")

            profile.hist_diabetes = bool(request.form.get("hist_diabetes"))
            profile.hist_hypertension = bool(request.form.get("hist_hypertension"))
            profile.hist_heart_disease = bool(request.form.get("hist_heart_disease"))
            profile.hist_kidney_disease = bool(request.form.get("hist_kidney_disease"))
            profile.hist_asthma = bool(request.form.get("hist_asthma"))
            profile.hist_thyroid = bool(request.form.get("hist_thyroid"))
            profile.allergies = request.form.get("allergies")
            profile.current_medications = request.form.get("current_medications")

            profile.fam_diabetes = bool(request.form.get("fam_diabetes"))
            profile.fam_heart_disease = bool(request.form.get("fam_heart_disease"))
            profile.fam_stroke = bool(request.form.get("fam_stroke"))
            profile.fam_cancer = bool(request.form.get("fam_cancer"))
            profile.fam_kidney_disease = bool(request.form.get("fam_kidney_disease"))

            db.session.commit()
            after_profile_saved(current_user)
            flash("Health profile saved.", "success")
            return redirect(url_for("dashboard"))

        return render_template("profile.html", profile=profile)

    # ---------- vitals / data entry ----------

    @app.route("/data-entry", methods=["GET", "POST"])
    @login_required
    def data_entry():
        if request.method == "POST":
            vitals = VitalSigns(
                user_id=current_user.id,
                systolic_bp=request.form.get("systolic_bp", type=int),
                diastolic_bp=request.form.get("diastolic_bp", type=int),
                blood_sugar=request.form.get("blood_sugar", type=float),
                heart_rate=request.form.get("heart_rate", type=int),
                oxygen_saturation=request.form.get("oxygen_saturation", type=int),
                body_temperature=request.form.get("body_temperature", type=float),
                cholesterol=request.form.get("cholesterol", type=float),
            )

            db.session.add(vitals)
            db.session.commit()

            alerts = check_emergency(vitals)
            after_vitals_saved(current_user, vitals, alerts)

            if alerts:
                flash("⚠️ Emergency alert triggered — check your dashboard.", "error")
            else:
                flash("Health data recorded.", "success")

            return redirect(url_for("dashboard"))

        return render_template("data_entry.html")

    # ---------- lab reports ----------

    @app.route("/labs", methods=["GET", "POST"])
    @login_required
    def labs():
        if request.method == "POST":
            lab = LabReport(
                user_id=current_user.id,
                hba1c=request.form.get("hba1c", type=float),
                fasting_blood_sugar=request.form.get("fasting_blood_sugar", type=float),
                total_cholesterol=request.form.get("total_cholesterol", type=float),
                hemoglobin=request.form.get("hemoglobin", type=float),
                creatinine=request.form.get("creatinine", type=float),
                liver_alt=request.form.get("liver_alt", type=float),
                kidney_egfr=request.form.get("kidney_egfr", type=float),
            )

            file = request.files.get("report_file")
            if file and file.filename:
                uploads_dir = os.path.join(
                    app.config["INSTANCE_DIR"], "uploads"
                )
                os.makedirs(uploads_dir, exist_ok=True)

                fname = (
                    f"user{current_user.id}_"
                    f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_"
                    f"{secure_filename(file.filename) or 'report'}"
                )
                fpath = os.path.join(uploads_dir, fname)
                file.save(fpath)
                lab.file_path = fname

            db.session.add(lab)
            db.session.commit()
            after_lab_saved(current_user, lab)
            flash("Lab report saved.", "success")
            return redirect(url_for("dashboard"))

        return render_template("labs.html")

    # ---------- symptoms ----------

    @app.route("/symptoms", methods=["GET", "POST"])
    @login_required
    def symptoms():
        if request.method == "POST":
            selected = request.form.getlist("symptoms")
            log = SymptomLog(
                user_id=current_user.id,
                symptoms=",".join(selected),
            )

            db.session.add(log)
            db.session.commit()
            after_symptoms_saved(current_user, log)
            flash("Symptoms recorded and analyzed.", "success")
            return redirect(url_for("dashboard"))

        return render_template(
            "symptoms.html",
            all_symptoms=list(SYMPTOM_MAP.keys()),
        )

    # ---------- dashboard ----------

    @app.route("/dashboard")
    @login_required
    def dashboard():
        if not current_user.profile:
            flash("Please complete your health profile first.", "info")
            return redirect(url_for("edit_profile"))

        data = compute_everything()

        # Save score history snapshot.
        hist = HealthScoreHistory(
            user_id=current_user.id,
            overall_score=data["scores"]["overall"],
            fitness_score=data["scores"]["fitness"]["score"],
            nutrition_score=data["scores"]["nutrition"]["score"],
            sleep_score=data["scores"]["sleep"]["score"],
            hydration_score=data["scores"]["hydration"]["score"],
            mental_score=data["scores"]["mental"]["score"],
        )
        db.session.add(hist)
        db.session.commit()

        history = [
            {
                "overall_score": h.overall_score,
                "fitness_score": h.fitness_score,
                "sleep_score": h.sleep_score,
            }
            for h in current_user.score_history[-12:]
        ]

        return render_template(
            "dashboard.html",
            profile=data["profile"],
            vitals=data["vitals"],
            scores=data["scores"],
            risks=data["risks"],
            symptom_result=data["symptom_result"],
            diet_plan=data["diet_plan"],
            exercise_plan=data["exercise_plan"],
            lifestyle_plan=data["lifestyle_plan"],
            preventive_care=data["preventive_care"],
            emergency_alerts=data["emergency_alerts"],
            history=history,
        )

    # ---------- AI coach ----------

    @app.route("/coach", methods=["GET", "POST"])
    @login_required
    def coach():
        if not current_user.profile:
            return redirect(url_for("edit_profile"))

        answer = None
        question = None

        if request.method == "POST":
            question = request.form.get("question", "")
            data = compute_everything()

            answer = answer_question(
                question,
                data["profile"],
                data["vitals"],
                data["scores"],
                data["risks"],
                data["diet_plan"],
                data["exercise_plan"],
            )

        return render_template(
            "coach.html",
            answer=answer,
            question=question,
        )

    @app.route("/coach/ask", methods=["POST"])
    @login_required
    def coach_ask():
        payload = request.get_json(force=True)
        question = payload.get("question", "")
        data = compute_everything()

        answer = answer_question(
            question,
            data["profile"],
            data["vitals"],
            data["scores"],
            data["risks"],
            data["diet_plan"],
            data["exercise_plan"],
        )

        return jsonify({"answer": answer})

    # ---------- PDF report ----------

    @app.route("/report/download")
    @login_required
    def download_report():
        data = compute_everything()

        if not data:
            flash("Please complete your health profile first.", "info")
            return redirect(url_for("edit_profile"))

        fname = (
            f"LifeTwin_Report_{current_user.id}_"
            f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf"
        )
        fpath = os.path.join(app.config["REPORTS_DIR"], fname)

        generate_pdf_report(
            fpath,
            current_user,
            data["profile"],
            data["vitals"],
            data["symptom_result"],
            data["scores"],
            data["risks"],
            data["diet_plan"],
            data["exercise_plan"],
            data["preventive_care"],
        )

        return send_file(
            fpath,
            as_attachment=True,
            download_name="LifeTwin_Health_Report.pdf",
        )

    # Register doctor / family / messaging / notifications routes.
    register_ecosystem(app)
    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        debug=os.environ.get("LIFETWIN_DEBUG", "0") == "1",
        host=os.environ.get("LIFETWIN_HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
    )
