"""
LifeTwin AI - Ecosystem models (Patient + Doctor + Family)
-----------------------------------------------------------
These tables are ADDED alongside the original models in models.py.
No original table or column is modified except the two additive columns
(role, phone) on `users`, which are handled by ecosystem.schema.
"""
from datetime import datetime

from models import db, User  # noqa: F401  (User imported so relationships resolve)

# ---------- role constants ----------
ROLE_PATIENT = "PATIENT"
ROLE_DOCTOR = "DOCTOR"
ROLE_FAMILY = "FAMILY"
ALL_ROLES = (ROLE_PATIENT, ROLE_DOCTOR, ROLE_FAMILY)

# ---------- doctor verification (application-level status only) ----------
VERIFY_PENDING = "PENDING"
VERIFY_VERIFIED = "VERIFIED"
VERIFY_REJECTED = "REJECTED"

# ---------- connection states ----------
CONN_PENDING = "PENDING"
CONN_ACCEPTED = "ACCEPTED"
CONN_REJECTED = "REJECTED"
CONN_BLOCKED = "BLOCKED"

# ---------- notification types ----------
N_CONNECTION = "CONNECTION"
N_MESSAGE = "MESSAGE"
N_DOCUMENT = "DOCUMENT"
N_EMERGENCY = "EMERGENCY"
N_HEALTH_UPDATE = "HEALTH_UPDATE"
N_FAMILY_ACCESS = "FAMILY_ACCESS"


class Doctor(db.Model):
    __tablename__ = "doctors"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    doctor_code = db.Column(db.String(20), unique=True)  # public "Doctor ID", e.g. DR-000012

    specialization = db.Column(db.String(120), nullable=False)
    qualification = db.Column(db.String(200), nullable=False)
    hospital = db.Column(db.String(200), nullable=False)
    experience_years = db.Column(db.Integer, default=0)
    license_number = db.Column(db.String(80), unique=True, nullable=False)
    bio = db.Column(db.Text)

    # Application-level status only. NOT an external license verification.
    verification_status = db.Column(db.String(20), nullable=False, default=VERIFY_PENDING)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("doctor_profile", uselist=False))

    @property
    def is_verified(self):
        return self.verification_status == VERIFY_VERIFIED


class DoctorPatientConnection(db.Model):
    __tablename__ = "doctor_patient_connections"
    __table_args__ = (db.UniqueConstraint("doctor_id", "patient_id", name="uq_doctor_patient"),)

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=CONN_PENDING)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime)
    accepted_at = db.Column(db.DateTime)

    doctor = db.relationship("Doctor", backref="connections")
    patient = db.relationship("User", foreign_keys=[patient_id], backref="doctor_connections")


class Conversation(db.Model):
    __tablename__ = "conversations"
    __table_args__ = (db.UniqueConstraint("doctor_id", "patient_id", name="uq_conversation_pair"),)

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    doctor = db.relationship("Doctor")
    patient = db.relationship("User", foreign_keys=[patient_id])
    messages = db.relationship("Message", backref="conversation", cascade="all, delete-orphan",
                               order_by="Message.id")


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False, index=True)
    sender_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.Text, nullable=False, default="")

    # Attachments are stored OUTSIDE the static folder and only served through
    # an authorized route. `attachment_stored_name` is a random server-side name.
    attachment_stored_name = db.Column(db.String(120))
    attachment_original_name = db.Column(db.String(255))
    attachment_mime = db.Column(db.String(100))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    read_at = db.Column(db.DateTime)

    sender = db.relationship("User", foreign_keys=[sender_user_id])


class FamilyMember(db.Model):
    __tablename__ = "family_members"
    __table_args__ = (db.UniqueConstraint("patient_id", "user_id", name="uq_family_link"),)

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    relationship_label = db.Column("relationship", db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    patient = db.relationship("User", foreign_keys=[patient_id], backref="family_links")
    member_user = db.relationship("User", foreign_keys=[user_id], backref="family_of")
    permission = db.relationship("FamilyPermission", backref="family_member", uselist=False,
                                 cascade="all, delete-orphan")


class FamilyPermission(db.Model):
    __tablename__ = "family_permissions"

    id = db.Column(db.Integer, primary_key=True)
    family_member_id = db.Column(db.Integer, db.ForeignKey("family_members.id"), unique=True, nullable=False)

    emergency_alerts = db.Column(db.Boolean, default=True, nullable=False)
    view_vitals = db.Column(db.Boolean, default=False, nullable=False)
    view_health_score = db.Column(db.Boolean, default=False, nullable=False)
    view_labs = db.Column(db.Boolean, default=False, nullable=False)
    view_history = db.Column(db.Boolean, default=False, nullable=False)   # medical history
    view_symptoms = db.Column(db.Boolean, default=False, nullable=False)
    view_doctor_conversations = db.Column(db.Boolean, default=False, nullable=False)  # read-only

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Ordered (field, label, help) used by both the UI and the validation code.
FAMILY_PERMISSION_FIELDS = [
    ("emergency_alerts", "Emergency Alerts", "Includes the abnormal reading that triggered the alert"),
    ("view_vitals", "Vital Signs", "Latest vitals and vital-sign trends"),
    ("view_health_score", "Health Score", "Overall and sub-scores"),
    ("view_labs", "Laboratory Reports", "Lab values (not the uploaded files)"),
    ("view_history", "Medical History", "Conditions, allergies, medications, family history"),
    ("view_symptoms", "Symptoms", "Logged symptoms"),
    ("view_doctor_conversations", "Doctor Conversations", "Read-only view; also shows connected doctor(s)"),
]
FAMILY_PERMISSION_KEYS = [f[0] for f in FAMILY_PERMISSION_FIELDS]


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    notification_type = db.Column(db.String(30), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(300))        # internal path only
    related_id = db.Column(db.Integer)      # e.g. conversation id (used to coalesce message notifications)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="notifications")


class EmergencyEvent(db.Model):
    """One row per vital-sign record that tripped the EXISTING emergency engine."""
    __tablename__ = "emergency_events"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    vital_id = db.Column(db.Integer, db.ForeignKey("vital_signs.id"))
    details = db.Column(db.Text, nullable=False)   # newline-separated alert lines from check_emergency()
    notified_summary = db.Column(db.String(500))   # human-readable "who was notified"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    patient = db.relationship("User", foreign_keys=[patient_id])

    @property
    def lines(self):
        return [l for l in (self.details or "").split("\n") if l]


class ProfileWeightLog(db.Model):
    """The original schema stores only the CURRENT weight, so a weight trend
    needs history. A row is written whenever the health profile is saved."""
    __tablename__ = "profile_weight_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    weight_kg = db.Column(db.Float, nullable=False)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
