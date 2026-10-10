from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- Ecosystem extension (additive, backward compatible) ---
    # Pre-existing users automatically become PATIENT (see ecosystem.schema).
    role = db.Column(db.String(20), nullable=False, default="PATIENT", server_default="PATIENT")
    phone = db.Column(db.String(30))

    profile = db.relationship("HealthProfile", backref="user", uselist=False, cascade="all, delete-orphan")
    vitals = db.relationship("VitalSigns", backref="user", cascade="all, delete-orphan", order_by="VitalSigns.recorded_at")
    labs = db.relationship("LabReport", backref="user", cascade="all, delete-orphan", order_by="LabReport.recorded_at")
    symptom_logs = db.relationship("SymptomLog", backref="user", cascade="all, delete-orphan", order_by="SymptomLog.recorded_at")
    score_history = db.relationship("HealthScoreHistory", backref="user", cascade="all, delete-orphan", order_by="HealthScoreHistory.recorded_at")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_patient(self):
        return (self.role or "PATIENT") == "PATIENT"

    @property
    def is_doctor(self):
        return self.role == "DOCTOR"

    @property
    def is_family(self):
        return self.role == "FAMILY"


class HealthProfile(db.Model):
    __tablename__ = "health_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    height_cm = db.Column(db.Float)
    weight_kg = db.Column(db.Float)

    smoking = db.Column(db.String(20))          # Never / Occasional / Regular
    alcohol = db.Column(db.String(20))          # Never / Occasional / Regular
    exercise_frequency = db.Column(db.String(30))  # None / 1-2x week / 3-5x week / Daily
    sleep_hours = db.Column(db.Float)
    water_intake_l = db.Column(db.Float)
    stress_level = db.Column(db.String(20))     # Low / Medium / High
    occupation = db.Column(db.String(120))

    # Medical history (booleans)
    hist_diabetes = db.Column(db.Boolean, default=False)
    hist_hypertension = db.Column(db.Boolean, default=False)
    hist_heart_disease = db.Column(db.Boolean, default=False)
    hist_kidney_disease = db.Column(db.Boolean, default=False)
    hist_asthma = db.Column(db.Boolean, default=False)
    hist_thyroid = db.Column(db.Boolean, default=False)
    allergies = db.Column(db.String(255))
    current_medications = db.Column(db.String(255))

    # Family history (booleans)
    fam_diabetes = db.Column(db.Boolean, default=False)
    fam_heart_disease = db.Column(db.Boolean, default=False)
    fam_stroke = db.Column(db.Boolean, default=False)
    fam_cancer = db.Column(db.Boolean, default=False)
    fam_kidney_disease = db.Column(db.Boolean, default=False)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def bmi(self):
        if self.height_cm and self.weight_kg:
            h_m = self.height_cm / 100
            return round(self.weight_kg / (h_m * h_m), 1)
        return None


class VitalSigns(db.Model):
    __tablename__ = "vital_signs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    systolic_bp = db.Column(db.Integer)
    diastolic_bp = db.Column(db.Integer)
    blood_sugar = db.Column(db.Float)       # mg/dL (random / fasting, self-reported)
    heart_rate = db.Column(db.Integer)      # bpm
    oxygen_saturation = db.Column(db.Integer)  # %
    body_temperature = db.Column(db.Float)  # Celsius
    cholesterol = db.Column(db.Float)       # optional, mg/dL

    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)


class LabReport(db.Model):
    __tablename__ = "lab_reports"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    hba1c = db.Column(db.Float)
    fasting_blood_sugar = db.Column(db.Float)
    total_cholesterol = db.Column(db.Float)
    hemoglobin = db.Column(db.Float)
    creatinine = db.Column(db.Float)
    liver_alt = db.Column(db.Float)   # ALT, liver function marker
    kidney_egfr = db.Column(db.Float)  # eGFR, kidney function marker
    file_path = db.Column(db.String(255))  # optional uploaded report file

    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)


class SymptomLog(db.Model):
    __tablename__ = "symptom_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    symptoms = db.Column(db.String(500))   # comma-separated list
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)


class HealthScoreHistory(db.Model):
    __tablename__ = "health_score_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    overall_score = db.Column(db.Integer)
    fitness_score = db.Column(db.Integer)
    nutrition_score = db.Column(db.Integer)
    sleep_score = db.Column(db.Integer)
    hydration_score = db.Column(db.Integer)
    mental_score = db.Column(db.Integer)

    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
