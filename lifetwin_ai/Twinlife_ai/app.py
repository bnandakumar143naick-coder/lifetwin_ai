"""
app.py - LifeTwin AI main Flask application.

Run with:  python app.py
Then open: http://127.0.0.1:5000
"""
import os
from functools import wraps
app=Flask(__name__)

from flask import (
    Flask, render_template, request, redirect, url_for, session, flash,
    jsonify, send_file
)
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_db, init_db, DB_PATH
import ai_engine
from pdf_generator import build_health_report_pdf

app = Flask(__name__)
app.secret_key = os.environ.get("LIFETWIN_SECRET_KEY", "dev-secret-key-change-in-production")

SYMPTOM_OPTIONS = list(ai_engine.SYMPTOM_CONDITION_MAP.keys())


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

@app.before_request
def ensure_db():
    if not os.path.exists(DB_PATH):
        init_db()


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Data access helpers
# ---------------------------------------------------------------------------

def get_user(user_id):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    db.close()
    return row


def get_profile(user_id):
    db = get_db()
    row = db.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    db.close()
    return dict(row) if row else {}


def get_latest_vitals(user_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM vitals WHERE user_id = ? ORDER BY recorded_at DESC, id DESC LIMIT 1", (user_id,)
    ).fetchone()
    db.close()
    return dict(row) if row else None


def get_vitals_history(user_id, limit=12):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM vitals WHERE user_id = ? ORDER BY recorded_at ASC, id ASC LIMIT ?", (user_id, limit)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_latest_lab(user_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM lab_reports WHERE user_id = ? ORDER BY recorded_at DESC, id DESC LIMIT 1", (user_id,)
    ).fetchone()
    db.close()
    return dict(row) if row else None


def get_latest_symptoms(user_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM symptoms_log WHERE user_id = ? ORDER BY recorded_at DESC, id DESC LIMIT 1", (user_id,)
    ).fetchone()
    db.close()
    if row and row["symptoms_csv"]:
        return [s for s in row["symptoms_csv"].split(",") if s]
    return []


def get_score_history(user_id, limit=12):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM health_scores WHERE user_id = ? ORDER BY computed_at ASC, id ASC LIMIT ?", (user_id, limit)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def save_score_snapshot(user_id, scores):
    db = get_db()
    db.execute(
        "INSERT INTO health_scores (user_id, overall, physical, nutrition, sleep, hydration, mental) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, scores["overall"], scores["physical"], scores["nutrition"],
         scores["sleep"], scores["hydration"], scores["mental"]),
    )
    db.commit()
    db.close()


def compute_full_analysis(user_id):
    """Runs the full AI pipeline for a user and returns everything the dashboard/report needs."""
    profile = get_profile(user_id)
    latest_vitals = get_latest_vitals(user_id)
    latest_lab = get_latest_lab(user_id)
    current_symptoms = get_latest_symptoms(user_id)

    scores = ai_engine.compute_health_scores(profile, latest_vitals)
    symptom_results, highest_symptom_risk = ai_engine.analyze_symptoms(current_symptoms, profile, latest_vitals)
    disease_risks = ai_engine.predict_disease_risks(profile, latest_vitals, latest_lab)
    plan = ai_engine.generate_prevention_plan(profile, disease_risks)
    alerts = ai_engine.check_emergency(latest_vitals)

    return {
        "profile": profile,
        "latest_vitals": latest_vitals,
        "latest_lab": latest_lab,
        "current_symptoms": current_symptoms,
        "scores": scores,
        "symptom_results": symptom_results,
        "highest_symptom_risk": highest_symptom_risk,
        "disease_risks": disease_risks,
        "plan": plan,
        "alerts": alerts,
    }


# ---------------------------------------------------------------------------
# Module 1: Auth (Registration / Login)
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        age = request.form.get("age") or None
        gender = request.form.get("gender") or None

        if not full_name or not email or not password:
            flash("Full name, email, and password are required.", "danger")
            return render_template("register.html")

        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            db.close()
            flash("An account with this email already exists.", "danger")
            return render_template("register.html")

        password_hash = generate_password_hash(password)
        cur = db.execute(
            "INSERT INTO users (full_name, email, password_hash, age, gender) VALUES (?, ?, ?, ?, ?)",
            (full_name, email, password_hash, age, gender),
        )
        user_id = cur.lastrowid
        db.execute("INSERT INTO profiles (user_id) VALUES (?)", (user_id,))
        db.commit()
        db.close()

        session["user_id"] = user_id
        session["full_name"] = full_name
        flash("Account created successfully! Let's build your Health Profile.", "success")
        return redirect(url_for("profile"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        db.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["full_name"] = user["full_name"]
            flash(f"Welcome back, {user['full_name']}!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")
        return render_template("login.html")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


# ---------------------------------------------------------------------------
# Module 2: Health Profile Creation
# ---------------------------------------------------------------------------

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user_id = session["user_id"]

    if request.method == "POST":
        def f(name):
            val = request.form.get(name)
            return float(val) if val not in (None, "") else None

        def checkbox(name):
            return 1 if request.form.get(name) == "on" else 0

        db = get_db()
        db.execute(
            """UPDATE profiles SET
                height_cm=?, weight_kg=?, smoking=?, alcohol=?, exercise_freq=?,
                sleep_hours=?, water_intake_l=?, stress_level=?, occupation=?,
                diabetes=?, hypertension=?, heart_disease=?, kidney_disease=?, asthma=?, thyroid_disease=?,
                allergies=?, current_medications=?,
                family_diabetes=?, family_heart_disease=?, family_stroke=?, family_cancer=?, family_kidney_disease=?,
                updated_at=datetime('now')
               WHERE user_id=?""",
            (
                f("height_cm"), f("weight_kg"),
                request.form.get("smoking"), request.form.get("alcohol"), request.form.get("exercise_freq"),
                f("sleep_hours"), f("water_intake_l"), request.form.get("stress_level"),
                request.form.get("occupation"),
                checkbox("diabetes"), checkbox("hypertension"), checkbox("heart_disease"),
                checkbox("kidney_disease"), checkbox("asthma"), checkbox("thyroid_disease"),
                request.form.get("allergies"), request.form.get("current_medications"),
                checkbox("family_diabetes"), checkbox("family_heart_disease"), checkbox("family_stroke"),
                checkbox("family_cancer"), checkbox("family_kidney_disease"),
                user_id,
            ),
        )
        db.commit()
        db.close()
        flash("Health profile updated successfully.", "success")
        return redirect(url_for("dashboard"))

    profile_data = get_profile(user_id)
    return render_template("profile.html", profile=profile_data)


# ---------------------------------------------------------------------------
# Module 3: Health Data Entry (Vitals)
# ---------------------------------------------------------------------------

@app.route("/data-entry", methods=["GET", "POST"])
@login_required
def data_entry():
    user_id = session["user_id"]

    if request.method == "POST":
        def f(name):
            val = request.form.get(name)
            return float(val) if val not in (None, "") else None

        db = get_db()
        db.execute(
            "INSERT INTO vitals (user_id, systolic, diastolic, blood_sugar, heart_rate, spo2, temperature, cholesterol) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, f("systolic"), f("diastolic"), f("blood_sugar"), f("heart_rate"),
             f("spo2"), f("temperature"), f("cholesterol")),
        )
        db.commit()
        db.close()
        flash("Health data recorded successfully.", "success")
        return redirect(url_for("dashboard"))

    latest = get_latest_vitals(user_id)
    return render_template("data_entry.html", latest=latest)


# ---------------------------------------------------------------------------
# Module 4: Laboratory Reports (Optional)
# ---------------------------------------------------------------------------

@app.route("/lab-reports", methods=["GET", "POST"])
@login_required
def lab_reports():
    user_id = session["user_id"]

    if request.method == "POST":
        def f(name):
            val = request.form.get(name)
            return float(val) if val not in (None, "") else None

        db = get_db()
        db.execute(
            "INSERT INTO lab_reports (user_id, hba1c, lab_cholesterol, hemoglobin, creatinine, liver_alt, liver_ast, kidney_egfr) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, f("hba1c"), f("lab_cholesterol"), f("hemoglobin"), f("creatinine"),
             f("liver_alt"), f("liver_ast"), f("kidney_egfr")),
        )
        db.commit()
        db.close()
        flash("Lab report values saved successfully.", "success")
        return redirect(url_for("dashboard"))

    latest = get_latest_lab(user_id)
    return render_template("lab_reports.html", latest=latest)


# ---------------------------------------------------------------------------
# Module 5: Current Symptoms
# ---------------------------------------------------------------------------

@app.route("/symptoms", methods=["GET", "POST"])
@login_required
def symptoms():
    user_id = session["user_id"]

    if request.method == "POST":
        selected = request.form.getlist("symptoms")
        db = get_db()
        db.execute(
            "INSERT INTO symptoms_log (user_id, symptoms_csv) VALUES (?, ?)",
            (user_id, ",".join(selected)),
        )
        db.commit()
        db.close()
        flash("Symptoms recorded. See your Symptom Analysis on the dashboard.", "success")
        return redirect(url_for("dashboard"))

    current = get_latest_symptoms(user_id)
    return render_template("symptoms.html", options=SYMPTOM_OPTIONS, current=current)


# ---------------------------------------------------------------------------
# Modules 6-11: Dashboard (Health Analysis, Symptom Analysis, Disease Risk,
# Prevention Plan, Emergency Detection, Dashboard display)
# ---------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    user = get_user(user_id)
    analysis = compute_full_analysis(user_id)

    # Save a score snapshot for monthly progress tracking (once per data change is fine for MVP)
    save_score_snapshot(user_id, analysis["scores"])

    score_history = get_score_history(user_id)
    vitals_history = get_vitals_history(user_id)

    return render_template(
        "dashboard.html",
        user=user,
        profile=analysis["profile"],
        scores=analysis["scores"],
        latest_vitals=analysis["latest_vitals"],
        current_symptoms=analysis["current_symptoms"],
        symptom_results=analysis["symptom_results"],
        disease_risks=analysis["disease_risks"],
        plan=analysis["plan"],
        alerts=analysis["alerts"],
        score_history=score_history,
        vitals_history=vitals_history,
    )


# ---------------------------------------------------------------------------
# Module 12: AI Health Coach
# ---------------------------------------------------------------------------

@app.route("/coach", methods=["GET"])
@login_required
def coach():
    return render_template("coach.html")


@app.route("/api/coach", methods=["POST"])
@login_required
def api_coach():
    user_id = session["user_id"]
    question = request.json.get("question", "") if request.is_json else request.form.get("question", "")

    analysis = compute_full_analysis(user_id)
    answer = ai_engine.ai_coach_answer(
        question, analysis["profile"], analysis["latest_vitals"], analysis["scores"], analysis["disease_risks"]
    )
    return jsonify({"answer": answer})


# ---------------------------------------------------------------------------
# Module 13: Download Health Report (PDF)
# ---------------------------------------------------------------------------

@app.route("/download-report")
@login_required
def download_report():
    user_id = session["user_id"]
    user = get_user(user_id)
    analysis = compute_full_analysis(user_id)

    pdf_buffer = build_health_report_pdf(
        user=user,
        profile=analysis["profile"],
        latest_vitals=analysis["latest_vitals"],
        scores=analysis["scores"],
        symptom_results=analysis["symptom_results"],
        disease_risks=analysis["disease_risks"],
        plan=analysis["plan"],
        alerts=analysis["alerts"],
    )

    filename = f"LifeTwinAI_Health_Report_{user['full_name'].replace(' ', '_')}.pdf"
    return send_file(pdf_buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")


# ---------------------------------------------------------------------------
# JSON API (used by dashboard charts)
# ---------------------------------------------------------------------------

@app.route("/api/score-history")
@login_required
def api_score_history():
    return jsonify(get_score_history(session["user_id"]))


@app.route("/api/vitals-history")
@login_required
def api_vitals_history():
    return jsonify(get_vitals_history(session["user_id"]))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
