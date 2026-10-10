"""
Optional: create DEMO accounts so you can try the whole ecosystem immediately.
    python seed_demo.py
DEMO PASSWORDS ARE PUBLIC — never run this against a real deployment.
"""
from app import app
from models import db, User, HealthProfile, VitalSigns, LabReport, SymptomLog
from models_ecosystem import (Doctor, DoctorPatientConnection, FamilyMember, FamilyPermission,
                              VERIFY_VERIFIED, CONN_ACCEPTED, ROLE_DOCTOR, ROLE_FAMILY)
from ecosystem.access import get_or_create_conversation
from datetime import datetime

with app.app_context():
    if User.query.filter_by(email="rahul@demo.com").first():
        print("Demo data already exists.")
        raise SystemExit

    rahul = User(full_name="Rahul", email="rahul@demo.com", age=24, gender="Male"); rahul.set_password("demo12345")
    doc_u = User(full_name="Priya Sharma", email="priya@demo.com", age=0, gender="N/A", role=ROLE_DOCTOR, phone="9000000001")
    doc_u.set_password("demo12345")
    dad = User(full_name="Suresh (Father)", email="father@demo.com", age=0, gender="N/A", role=ROLE_FAMILY); dad.set_password("demo12345")
    db.session.add_all([rahul, doc_u, dad]); db.session.flush()

    db.session.add(HealthProfile(user_id=rahul.id, height_cm=175, weight_kg=72, smoking="Never", alcohol="Occasional",
                                 exercise_frequency="3-5x week", sleep_hours=7, water_intake_l=2.2, stress_level="Medium"))
    db.session.add(VitalSigns(user_id=rahul.id, systolic_bp=125, diastolic_bp=80, blood_sugar=95, heart_rate=74,
                              oxygen_saturation=98, body_temperature=36.7))
    db.session.add(LabReport(user_id=rahul.id, hba1c=5.4, total_cholesterol=180, creatinine=0.9, kidney_egfr=105))
    db.session.add(SymptomLog(user_id=rahul.id, symptoms="Headache,Fatigue"))

    doc = Doctor(user_id=doc_u.id, specialization="Cardiologist", qualification="MBBS, MD (Cardiology)",
                 hospital="ABC Hospital", experience_years=12, license_number="DEMO-0001",
                 verification_status=VERIFY_VERIFIED)
    db.session.add(doc); db.session.flush()
    doc.doctor_code = f"DR-{doc.id:06d}"
    now = datetime.utcnow()
    db.session.add(DoctorPatientConnection(doctor_id=doc.id, patient_id=rahul.id, status=CONN_ACCEPTED,
                                           requested_at=now, responded_at=now, accepted_at=now))
    get_or_create_conversation(doc.id, rahul.id)
    fm = FamilyMember(patient_id=rahul.id, user_id=dad.id, relationship_label="Father")
    fm.permission = FamilyPermission(emergency_alerts=True, view_vitals=True, view_health_score=True)
    db.session.add(fm)
    db.session.commit()
    print("Demo created:\n  Patient : rahul@demo.com   / demo12345   (/login)\n"
          "  Doctor  : priya@demo.com   / demo12345   (/doctor/login)\n"
          "  Family  : father@demo.com  / demo12345   (/family/login)")
