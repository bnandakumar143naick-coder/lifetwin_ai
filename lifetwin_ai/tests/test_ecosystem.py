"""
End-to-end tests for the Patient + Doctor + Family ecosystem.
Run from the project root:   python -m unittest tests.test_ecosystem -v
Uses a temporary SQLite database; never touches instance/lifetwin.db.
"""
import io
import os
import re
import sys
import tempfile
import unittest

_TMP = tempfile.mkdtemp(prefix="lifetwin_test_")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_TMP, "test.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as lifetwin  # noqa: E402
from models import db, User, LabReport  # noqa: E402
from models_ecosystem import (  # noqa: E402
    Doctor, DoctorPatientConnection, Message, Notification, EmergencyEvent, FamilyMember,
    Conversation,
)

APP = lifetwin.app
APP.config["ATTACHMENTS_DIR"] = os.path.join(_TMP, "attachments")
APP.config["TESTING"] = True
TOKEN = "test-csrf-token"

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def client():
    c = APP.test_client()
    with c.session_transaction() as s:
        s["_csrf_token"] = TOKEN
    return c


def post(c, url, data=None, **kw):
    d = {"csrf_token": TOKEN}
    d.update(data or {})
    return c.post(url, data=d, **kw)


def register_patient(c, name, email, age=30):
    r = c.post("/register", data={"full_name": name, "email": email, "password": "patientpw1",
                                  "age": age, "gender": "Male"})
    assert r.status_code == 302, r.data
    c.post("/profile", data={"height_cm": 175, "weight_kg": 70, "smoking": "Never", "alcohol": "Never",
                             "exercise_frequency": "3-5x week", "sleep_hours": 7.5, "water_intake_l": 2.5,
                             "stress_level": "Low", "occupation": "x"})


def register_doctor(c, name, email, lic, spec="Cardiologist", hosp="ABC Hospital"):
    return post(c, "/doctor/register", {
        "full_name": name, "email": email, "phone": "9999999999", "password": "doctorpw1",
        "specialization": spec, "qualification": "MBBS, MD", "hospital": hosp,
        "experience_years": 12, "license_number": lic})


def verify(email):
    from ecosystem.cli import _set
    with APP.app_context():
        _set(email, "VERIFIED")


def uid(email):
    with APP.app_context():
        return User.query.filter_by(email=email).first().id


def did(email):
    with APP.app_context():
        return User.query.filter_by(email=email).first().doctor_profile.id


class Ecosystem(unittest.TestCase):
    """Tests share one database; each builds only on state it creates itself
    (unique emails) so ordering does not matter."""

    # ---------------- roles / legacy ----------------
    def test_01_patient_flow_and_legacy_features(self):
        c = client()
        register_patient(c, "Rahul", "rahul@t.com", 24)
        with APP.app_context():
            self.assertEqual(User.query.filter_by(email="rahul@t.com").first().role, "PATIENT")
        for url in ["/dashboard", "/profile", "/data-entry", "/labs", "/symptoms", "/coach",
                    "/doctors", "/messages", "/my-family", "/emergency", "/account", "/notifications"]:
            self.assertEqual(c.get(url).status_code, 200, url)
        d = c.get("/dashboard").data.decode()
        for marker in ["Overall Health Score", "Future Disease Risk", "Personalized Diet Plan",
                       'id="health-score"', 'id="risk-analysis"', 'id="plans"']:
            self.assertIn(marker, d)
        r = c.get("/report/download")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.startswith(b"%PDF"))
        r = c.post("/coach/ask", json={"question": "Why is my blood pressure high?"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("answer", r.get_json())
        r = c.post("/symptoms", data={"symptoms": ["Headache", "Fatigue"]})
        self.assertEqual(r.status_code, 302)
        r = c.post("/labs", data={"hba1c": "5.4", "total_cholesterol": "180"})
        self.assertEqual(r.status_code, 302)

    def test_02_invalid_patient_login(self):
        c = client()
        r = c.post("/login", data={"email": "nobody@t.com", "password": "x"})
        self.assertIn(b"Invalid email or password", r.data)

    def test_03_legacy_pages_blocked_for_doctor_and_family(self):
        c = client()
        register_doctor(c, "Dr Guard", "guard@t.com", "LIC-GUARD")
        for url in ["/dashboard", "/data-entry", "/labs", "/symptoms", "/coach", "/report/download", "/profile"]:
            r = c.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn("/doctor/dashboard", r.headers["Location"])
        r = c.post("/coach/ask", json={"question": "hi"})
        self.assertEqual(r.status_code, 403)

    # ---------------- doctor auth ----------------
    def test_10_doctor_registration_validation_and_duplicates(self):
        c = client()
        r = register_doctor(c, "Dr Priya Sharma", "priya@t.com", "MCI-1001")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/doctor/dashboard", r.headers["Location"])
        with APP.app_context():
            d = User.query.filter_by(email="priya@t.com").first().doctor_profile
            self.assertEqual(d.verification_status, "PENDING")
            self.assertTrue(d.doctor_code.startswith("DR-"))
        c2 = client()
        r = register_doctor(c2, "Other", "priya@t.com", "MCI-2222")
        self.assertIn(b"already exists", r.data)                       # duplicate email
        r = register_doctor(c2, "Other", "other1@t.com", "mci-1001")
        self.assertIn(b"already exists", r.data)                       # duplicate licence (case-insensitive)
        r = post(c2, "/doctor/register", {"full_name": "X", "email": "x@t.com", "phone": "1", "password": "short",
                                          "specialization": "a", "qualification": "b", "hospital": "c",
                                          "experience_years": 1, "license_number": "L9"})
        self.assertIn(b"at least 8", r.data)                            # weak password
        r = post(c2, "/doctor/register", {"full_name": "X"})
        self.assertIn(b"fill in all fields", r.data)

    def test_11_doctor_login_logout_and_wrong_portal(self):
        c = client()
        register_doctor(c, "Dr Login", "dlogin@t.com", "LIC-LOGIN")
        c.get("/logout")
        r = post(c, "/doctor/login", {"email": "dlogin@t.com", "password": "bad"})
        self.assertIn(b"Invalid email or password", r.data)
        r = post(c, "/doctor/login", {"email": "dlogin@t.com", "password": "doctorpw1"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(c.get("/doctor/dashboard").status_code, 200)
        c.get("/logout")
        self.assertEqual(c.get("/doctor/dashboard").status_code, 302)   # logged out -> redirected to login
        # a PATIENT cannot use the doctor portal even with a correct password
        p = client()
        register_patient(p, "Pat Portal", "pportal@t.com")
        p.get("/logout")
        r = post(p, "/doctor/login", {"email": "pportal@t.com", "password": "patientpw1"})
        self.assertIn(b"not registered for this portal", r.data)
        self.assertEqual(p.get("/doctor/dashboard").status_code, 302)

    def test_12_unverified_doctor_hidden_and_powerless(self):
        d = client()
        register_doctor(d, "Dr Pending", "pending@t.com", "LIC-PEND", spec="Neurologist")
        p = client()
        register_patient(p, "Pat Search", "psearch@t.com")
        self.assertNotIn(b"Dr. Dr Pending", p.get("/doctors?q=Neurologist").data)
        r = post(p, f"/doctors/{did('pending@t.com')}/request")
        self.assertEqual(r.status_code, 302)
        with APP.app_context():
            self.assertEqual(DoctorPatientConnection.query.filter_by(doctor_id=did('pending@t.com')).count(), 0)
        self.assertIn(b"PENDING", d.get("/doctor/dashboard").data)

    # ---------------- search / connection lifecycle ----------------
    def _verified_doctor(self, name, email, lic, spec="Cardiologist", hosp="ABC Hospital"):
        c = client()
        register_doctor(c, name, email, lic, spec, hosp)
        verify(email)
        return c

    def test_20_search_variants(self):
        self._verified_doctor("Priya Searchable", "ps@t.com", "LIC-S1", "Dermatologist", "Zenith Clinic")
        p = client()
        register_patient(p, "Pat S", "pats@t.com")
        code = None
        with APP.app_context():
            code = User.query.filter_by(email="ps@t.com").first().doctor_profile.doctor_code
        for q in ["Priya Searchable", "dermatolo", "zenith", code, code.lower()]:
            self.assertIn(b"Priya Searchable", p.get("/doctors", query_string={"q": q}).data, q)
        self.assertNotIn(b"Priya Searchable", p.get("/doctors", query_string={"q": "%"}).data)   # wildcard is escaped
        self.assertIn(b"No verified doctors match", p.get("/doctors", query_string={"q": "zzzznone"}).data)

    def test_21_request_accept_reject_block_and_states(self):
        dc = self._verified_doctor("Dr Flow", "flow@t.com", "LIC-FLOW")
        pc = client()
        register_patient(pc, "Pat Flow", "pflow@t.com", 31)
        did_ = did("flow@t.com")
        r = post(pc, f"/doctors/{did_}/request")
        self.assertEqual(r.status_code, 302)
        r = post(pc, f"/doctors/{did_}/request", follow_redirects=True)
        self.assertIn(b"already have a pending request", r.data)          # duplicate request
        # doctor sees request with patient name + age, no health data
        page = dc.get("/doctor/requests").data.decode()
        self.assertIn("Pat Flow", page)
        self.assertIn("Age 31", page)
        # BEFORE accept: no access
        self.assertEqual(dc.get(f"/doctor/patient/{uid('pflow@t.com')}").status_code, 403)
        with APP.app_context():
            cid = DoctorPatientConnection.query.filter_by(doctor_id=did_).first().id
        r = post(dc, f"/doctor/requests/{cid}/accept")
        self.assertEqual(r.status_code, 302)
        with APP.app_context():
            c_ = db.session.get(DoctorPatientConnection, cid)
            self.assertEqual(c_.status, "ACCEPTED")
            self.assertIsNotNone(c_.accepted_at)
            self.assertEqual(Notification.query.filter_by(user_id=uid("pflow@t.com"), notification_type="CONNECTION").count(), 1)
        # AFTER accept: access granted
        r = dc.get(f"/doctor/patient/{uid('pflow@t.com')}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Health score", r.data)
        # patient disconnects -> access removed again
        post(pc, f"/connections/{cid}/remove")
        self.assertEqual(dc.get(f"/doctor/patient/{uid('pflow@t.com')}").status_code, 403)
        # re-request after REJECTED works; doctor blocks -> further requests refused
        post(pc, f"/doctors/{did_}/request")
        post(dc, f"/doctor/requests/{cid}/block")
        with APP.app_context():
            self.assertEqual(db.session.get(DoctorPatientConnection, cid).status, "BLOCKED")
        r = post(pc, f"/doctors/{did_}/request", follow_redirects=True)
        self.assertIn(b"cannot send a request", r.data)
        self.assertEqual(dc.get(f"/doctor/patient/{uid('pflow@t.com')}").status_code, 403)

    def test_22_reject(self):
        dc = self._verified_doctor("Dr Reject", "rej@t.com", "LIC-REJ")
        pc = client()
        register_patient(pc, "Pat Rej", "prej@t.com")
        post(pc, f"/doctors/{did('rej@t.com')}/request")
        with APP.app_context():
            cid = DoctorPatientConnection.query.filter_by(doctor_id=did('rej@t.com')).first().id
        post(dc, f"/doctor/requests/{cid}/reject")
        with APP.app_context():
            self.assertEqual(db.session.get(DoctorPatientConnection, cid).status, "REJECTED")
        self.assertEqual(dc.get(f"/doctor/patient/{uid('prej@t.com')}").status_code, 403)

    # ---------------- authorization ----------------
    def _connected_pair(self, dname, demail, lic, pname, pemail):
        dc = self._verified_doctor(dname, demail, lic)
        pc = client()
        register_patient(pc, pname, pemail)
        post(pc, f"/doctors/{did(demail)}/request")
        with APP.app_context():
            cid = DoctorPatientConnection.query.filter_by(doctor_id=did(demail), patient_id=uid(pemail)).first().id
        post(dc, f"/doctor/requests/{cid}/accept")
        return dc, pc, cid

    def test_30_url_guessing_and_cross_role_access(self):
        dcA, pcA, _ = self._connected_pair("Dr A", "da@t.com", "LIC-A", "Pat A", "pa@t.com")
        dcB = self._verified_doctor("Dr B", "db@t.com", "LIC-B")
        pcB = client()
        register_patient(pcB, "Pat B", "pb@t.com")
        pa, pb = uid("pa@t.com"), uid("pb@t.com")
        # doctor A CAN see their patient, but NOT patient B just by knowing the id
        self.assertEqual(dcA.get(f"/doctor/patient/{pa}").status_code, 200)
        for path in ["", "/history", "/timeline", "/report"]:
            self.assertEqual(dcA.get(f"/doctor/patient/{pb}{path}").status_code, 403, path)
            self.assertEqual(dcB.get(f"/doctor/patient/{pa}{path}").status_code, 403, path)
        self.assertEqual(dcA.get("/doctor/patient/999999").status_code, 403)          # missing patient == same 403
        self.assertEqual(dcA.get(f"/doctor/messages/{pb}").status_code, 403)
        # a doctor id passed as patient id is not a patient
        self.assertEqual(dcA.get(f"/doctor/patient/{uid('db@t.com')}").status_code, 403)
        # patients cannot enter the doctor portal / see other patients
        self.assertEqual(pcA.get("/doctor/dashboard").status_code, 403)
        self.assertEqual(pcA.get(f"/doctor/patient/{pa}").status_code, 403)
        # doctors cannot use patient-only new pages
        for url in ["/doctors", "/messages", "/my-family", "/emergency"]:
            self.assertEqual(dcA.get(url).status_code, 403, url)
        # anonymous
        anon = client()
        self.assertEqual(anon.get(f"/doctor/patient/{pa}").status_code, 302)
        self.assertEqual(anon.get("/messages").status_code, 302)

    def test_31_revoked_verification_removes_access(self):
        dc, pc, _ = self._connected_pair("Dr Rev", "drev@t.com", "LIC-REV", "Pat Rev", "prev@t.com")
        self.assertEqual(dc.get(f"/doctor/patient/{uid('prev@t.com')}").status_code, 200)
        from ecosystem.cli import _set
        with APP.app_context():
            _set("drev@t.com", "REJECTED")
        self.assertEqual(dc.get(f"/doctor/patient/{uid('prev@t.com')}").status_code, 403)
        self.assertEqual(pc.get(f"/messages/{did('drev@t.com')}").status_code, 403)

    def test_32_csrf_enforced_on_new_routes(self):
        pc = client()
        register_patient(pc, "Pat Csrf", "pcsrf@t.com")
        r = pc.post("/my-family/add", data={"full_name": "X", "email": "x@x.com", "relationship": "Dad", "password": "password1"})
        self.assertEqual(r.status_code, 400)
        r = pc.post("/my-family/add", data={"csrf_token": "wrong", "full_name": "X", "email": "x@x.com",
                                            "relationship": "Dad", "password": "password1"})
        self.assertEqual(r.status_code, 400)

    # ---------------- doctor view reuses existing engines ----------------
    def test_40_doctor_view_matches_patient_dashboard_numbers(self):
        dc, pc, _ = self._connected_pair("Dr Engine", "eng@t.com", "LIC-ENG", "Pat Engine", "peng@t.com")
        pc.post("/data-entry", data={"systolic_bp": 125, "diastolic_bp": 80, "heart_rate": 74,
                                     "oxygen_saturation": 98, "body_temperature": 36.7, "blood_sugar": 95})
        pc.post("/labs", data={"hba1c": "5.4", "total_cholesterol": "180", "creatinine": "0.9", "kidney_egfr": "105"})
        pc.post("/symptoms", data={"symptoms": ["Headache", "Fatigue"]})
        pd = pc.get("/dashboard").data.decode()
        dd = dc.get(f"/doctor/patient/{uid('peng@t.com')}").data.decode()
        # same overall score in both
        score = re.search(r'<div class="inner">(\d+)</div>\s*</div>\s*<h4>Overall', pd).group(1)
        self.assertIn(f'<div class="inner">{score}</div>', dd)
        for needle in ["125/80", "5.4", "Headache", "Hypertension", "Diabetes"]:
            self.assertIn(needle, dd, needle)
        # engine module identity: no second calculation engine
        import ecosystem.twin as twin_mod
        self.assertIs(twin_mod.compute_all_scores, __import__("utils.health_score", fromlist=["x"]).compute_all_scores)
        # read-only: viewing must not write a score-history row
        with APP.app_context():
            before = db.session.get(User, uid("peng@t.com")).score_history.__len__()
        dc.get(f"/doctor/patient/{uid('peng@t.com')}")
        with APP.app_context():
            after = db.session.get(User, uid("peng@t.com")).score_history.__len__()
        self.assertEqual(before, after)
        # history, timeline, PDF
        self.assertEqual(dc.get(f"/doctor/patient/{uid('peng@t.com')}/history").status_code, 200)
        tl = dc.get(f"/doctor/patient/{uid('peng@t.com')}/timeline").data.decode()
        for needle in ["New vitals recorded", "Symptoms recorded", "Doctor connection accepted"]:
            self.assertIn(needle, tl)
        r = dc.get(f"/doctor/patient/{uid('peng@t.com')}/report")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.startswith(b"%PDF"))
        # doctor dashboard stats + patient list
        dash = dc.get("/doctor/dashboard").data.decode()
        self.assertIn("Pat Engine", dash)
        # doctor got a "new health data" notification
        with APP.app_context():
            n = Notification.query.filter_by(user_id=uid("eng@t.com"), notification_type="HEALTH_UPDATE").count()
            self.assertGreaterEqual(n, 1)

    # ---------------- messaging ----------------
    def test_50_messaging_read_status_polling_and_validation(self):
        dc, pc, _ = self._connected_pair("Dr Chat", "chat@t.com", "LIC-CHAT", "Pat Chat", "pchat@t.com")
        d, p = did("chat@t.com"), uid("pchat@t.com")
        r = post(dc, f"/doctor/messages/{p}", {"message": "Please upload your latest blood pressure reading."})
        self.assertEqual(r.status_code, 302)
        with APP.app_context():
            m = Message.query.first()
            self.assertFalse(Message.query.filter_by(message="Please upload your latest blood pressure reading.").first().is_read)
            self.assertEqual(Notification.query.filter_by(user_id=p, notification_type="MESSAGE").count(), 1)
        self.assertIn(b"1", pc.get("/messages").data)                              # unread badge/count present
        page = pc.get(f"/messages/{d}").data.decode()                              # opening marks read
        self.assertIn("Please upload your latest blood pressure reading.", page)
        with APP.app_context():
            self.assertTrue(Message.query.filter_by(message="Please upload your latest blood pressure reading.").first().is_read)
        post(pc, f"/messages/{d}", {"message": "My BP is 145/92."})
        # coalescing: second unread message does not create another notification
        post(pc, f"/messages/{d}", {"message": "Second message"})
        with APP.app_context():
            self.assertEqual(Notification.query.filter_by(user_id=uid("chat@t.com"), notification_type="MESSAGE", is_read=False).count(), 1)
            conv_id = Conversation.query.filter_by(patient_id=p).first().id
        r = dc.get(f"/api/conversations/{conv_id}/messages?after=0")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.get_json()["messages"]), 3)
        # validation
        r = post(pc, f"/messages/{d}", {"message": "   "}, follow_redirects=True)
        self.assertIn(b"Type a message or attach a file", r.data)
        r = post(pc, f"/messages/{d}", {"message": "x" * 2001}, follow_redirects=True)
        self.assertIn(b"too long", r.data)
        # XSS: message content is escaped
        post(pc, f"/messages/{d}", {"message": "<script>alert(1)</script>"})
        self.assertNotIn(b"<script>alert(1)</script>", dc.get(f"/doctor/messages/{p}").data)
        # outsiders cannot use the API or the thread
        other = self._verified_doctor("Dr Out", "out@t.com", "LIC-OUT")
        self.assertEqual(other.get(f"/api/conversations/{conv_id}/messages").status_code, 403)
        self.assertEqual(other.get(f"/doctor/messages/{p}").status_code, 403)
        pother = client()
        register_patient(pother, "Pat Out", "pout@t.com")
        self.assertEqual(pother.get(f"/api/conversations/{conv_id}/messages").status_code, 403)
        self.assertEqual(pother.get(f"/messages/{d}").status_code, 403)
        self.assertEqual(client().get(f"/api/conversations/{conv_id}/messages").status_code, 401)

    def test_51_attachments_secure(self):
        dc, pc, _ = self._connected_pair("Dr File", "file@t.com", "LIC-FILE", "Pat File", "pfile@t.com")
        d, p = did("file@t.com"), uid("pfile@t.com")
        r = pc.post(f"/messages/{d}", data={"csrf_token": TOKEN, "message": "report",
                                            "attachment": (io.BytesIO(PDF), "Blood_Test_Report.pdf")},
                    content_type="multipart/form-data")
        self.assertEqual(r.status_code, 302)
        with APP.app_context():
            m = Message.query.filter_by(attachment_original_name="Blood_Test_Report.pdf").first()
            self.assertIsNotNone(m)
            stored, mid = m.attachment_stored_name, m.id
            self.assertNotIn("Blood_Test", stored)                                    # random server-side name
            self.assertEqual(Notification.query.filter_by(user_id=uid("file@t.com"), notification_type="DOCUMENT").count(), 1)
        self.assertEqual(dc.get(f"/attachments/{mid}").status_code, 200)              # recipient doctor
        self.assertEqual(pc.get(f"/attachments/{mid}").status_code, 200)              # sender patient
        self.assertEqual(self._verified_doctor("Dr Nosy", "nosy@t.com", "LIC-NOSY").get(f"/attachments/{mid}").status_code, 403)
        pn = client(); register_patient(pn, "Pat Nosy", "pnosy@t.com")
        self.assertEqual(pn.get(f"/attachments/{mid}").status_code, 403)
        self.assertEqual(client().get(f"/attachments/{mid}").status_code, 302)
        self.assertEqual(APP.test_client().get(f"/static/../instance/attachments/{stored}").status_code, 404)  # not public
        # rejected uploads
        def up(data, name):
            return pc.post(f"/messages/{d}", data={"csrf_token": TOKEN, "message": "", "attachment": (io.BytesIO(data), name)},
                           content_type="multipart/form-data", follow_redirects=True).data
        self.assertIn(b"not allowed", up(b"MZ..", "evil.exe"))
        self.assertIn(b"does not match", up(b"<html>", "fake.pdf"))                    # wrong magic bytes
        self.assertIn(b"too large", up(PDF + b"0" * (5 * 1024 * 1024), "big.pdf"))
        self.assertIn(b"empty", up(b"", "empty.pdf"))
        # png accepted (doctor -> patient direction)
        r = dc.post(f"/doctor/messages/{p}", data={"csrf_token": TOKEN, "message": "", "attachment": (io.BytesIO(PNG), "Instructions.png")},
                    content_type="multipart/form-data")
        self.assertEqual(r.status_code, 302)
        with APP.app_context():
            self.assertEqual(Notification.query.filter_by(user_id=p, notification_type="DOCUMENT").count(), 1)

    # ---------------- family ----------------
    def _add_family(self, pc, name, email, rel, perms, pw="familypw1"):
        data = {"full_name": name, "email": email, "relationship": rel, "password": pw}
        data.update({k: "on" for k in perms})
        return post(pc, "/my-family/add", data)

    def test_60_family_permissions_enforced_on_backend(self):
        pc = client()
        register_patient(pc, "Pat Fam", "pfam@t.com", 24)
        pc.post("/data-entry", data={"systolic_bp": 125, "diastolic_bp": 80, "heart_rate": 74, "oxygen_saturation": 98})
        pc.post("/labs", data={"hba1c": "6.13", "total_cholesterol": "187"})
        pc.post("/symptoms", data={"symptoms": ["Headache"]})
        pc.post("/profile", data={"height_cm": 175, "weight_kg": 70, "smoking": "Never", "alcohol": "Never",
                                  "exercise_frequency": "3-5x week", "sleep_hours": 7.5, "water_intake_l": 2.5,
                                  "stress_level": "Low", "allergies": "PenicillinXYZ", "hist_diabetes": "on"})
        self.assertEqual(self._add_family(pc, "Father Fam", "father@t.com", "Father",
                                          ["emergency_alerts", "view_vitals", "view_health_score"]).status_code, 302)
        self.assertEqual(self._add_family(pc, "Mother Fam", "mother@t.com", "Mother",
                                          ["emergency_alerts", "view_vitals", "view_health_score", "view_labs",
                                           "view_history", "view_symptoms"]).status_code, 302)
        with APP.app_context():
            self.assertEqual(FamilyMember.query.filter_by(patient_id=uid("pfam@t.com")).count(), 2)
            self.assertEqual(User.query.filter_by(email="father@t.com").first().role, "FAMILY")

        father = client(); mother = client()
        self.assertEqual(post(father, "/family/login", {"email": "father@t.com", "password": "familypw1"}).status_code, 302)
        post(mother, "/family/login", {"email": "mother@t.com", "password": "familypw1"})

        # FATHER: vitals + score + alerts only
        dash = father.get("/family/dashboard").data.decode()
        self.assertIn("125/80", dash); self.assertIn("/ 100", dash)
        self.assertEqual(father.get("/family/vitals").status_code, 200)
        self.assertEqual(father.get("/family/alerts").status_code, 200)
        self.assertEqual(father.get("/family/conversations").status_code, 403)
        health = father.get("/family/health").data.decode()
        for secret in ["6.13", "187", "PenicillinXYZ", "Headache", "Diabetes"]:
            self.assertNotIn(secret, health, f"father must not see {secret}")
        upd = father.get("/family/updates").data.decode()
        self.assertNotIn("Headache", upd); self.assertNotIn("Lab", upd)
        self.assertIn("New vitals recorded", upd)
        # MOTHER: everything except conversations
        mh = mother.get("/family/health").data.decode()
        for seen in ["6.13", "187", "PenicillinXYZ", "Headache", "Diabetes"]:
            self.assertIn(seen, mh, f"mother should see {seen}")
        self.assertEqual(mother.get("/family/conversations").status_code, 403)

        # Family can't touch other roles' pages or other patients' links
        for url in ["/dashboard", "/doctors", "/messages", "/my-family", "/doctor/dashboard", "/data-entry"]:
            self.assertIn(father.get(url).status_code, (302, 403), url)
        self.assertEqual(father.get("/family/dashboard").status_code, 200)

        # Patient changes permissions -> immediate effect on the server
        with APP.app_context():
            father_link = FamilyMember.query.filter_by(user_id=uid("father@t.com")).first().id
        post(pc, f"/my-family/{father_link}/permissions", {"emergency_alerts": "on"})   # everything else off
        self.assertEqual(father.get("/family/vitals").status_code, 403)
        self.assertNotIn("125/80", father.get("/family/dashboard").data.decode())
        post(pc, f"/my-family/{father_link}/permissions", {"emergency_alerts": "on", "view_doctor_conversations": "on"})
        self.assertEqual(father.get("/family/conversations").status_code, 200)
        # A different patient cannot edit this patient's family links
        other = client(); register_patient(other, "Pat Other", "pother@t.com")
        self.assertEqual(post(other, f"/my-family/{father_link}/permissions", {"view_labs": "on"}).status_code, 403)
        self.assertEqual(post(other, f"/my-family/{father_link}/remove").status_code, 403)
        # Removal revokes everything instantly
        post(pc, f"/my-family/{father_link}/remove")
        gone = father.get("/family/dashboard").data.decode()
        self.assertNotIn("Pat Fam", gone); self.assertIn("No patient linked yet", gone)
        for url in ["/family/health", "/family/vitals", "/family/alerts", "/family/updates", "/family/conversations"]:
            r = father.get(url)
            self.assertEqual(r.status_code, 302, url)                      # no link left -> bounced to dashboard
            self.assertIn("/family/dashboard", r.headers["Location"])
        with APP.app_context():
            self.assertIsNone(db.session.get(FamilyMember, father_link))    # link + permission rows are gone

    def test_61_family_input_validation(self):
        pc = client(); register_patient(pc, "Pat FV", "pfv@t.com")
        r = post(pc, "/my-family/add", {"full_name": "A", "email": "bad-email", "relationship": "Dad", "password": "password1"}, follow_redirects=True)
        self.assertIn(b"valid email", r.data)
        r = post(pc, "/my-family/add", {"full_name": "A", "email": "shortpw@t.com", "relationship": "Dad", "password": "123"}, follow_redirects=True)
        self.assertIn(b"at least 8", r.data)
        r = post(pc, "/my-family/add", {"full_name": "A", "email": "pfv@t.com", "relationship": "Dad", "password": "password1"}, follow_redirects=True)
        self.assertIn(b"different kind of account", r.data)             # cannot hijack a patient account
        self._add_family(pc, "Dup", "dupfam@t.com", "Dad", [])
        r = self._add_family(pc, "Dup", "dupfam@t.com", "Dad", [])
        r = post(pc, "/my-family/add", {"full_name": "Dup", "email": "dupfam@t.com", "relationship": "Dad"}, follow_redirects=True)
        self.assertIn(b"already added", r.data)
        # doctor email can't become a family login
        register_doctor(client(), "Dr Fam", "drfam@t.com", "LIC-FAMD")
        r = post(pc, "/my-family/add", {"full_name": "D", "email": "drfam@t.com", "relationship": "Dad", "password": "password1"}, follow_redirects=True)
        self.assertIn(b"different kind of account", r.data)
        # wrong portal
        f = client()
        r = post(f, "/family/login", {"email": "pfv@t.com", "password": "patientpw1"})
        self.assertIn(b"not registered for this portal", r.data)

    def test_62_one_family_login_can_link_multiple_patients(self):
        p1 = client(); register_patient(p1, "Pat M1", "pm1@t.com")
        p2 = client(); register_patient(p2, "Pat M2", "pm2@t.com")
        self._add_family(p1, "Shared Fam", "shared@t.com", "Sister", ["view_vitals"])
        post(p2, "/my-family/add", {"full_name": "Shared Fam", "email": "shared@t.com", "relationship": "Brother", "view_health_score": "on"})
        with APP.app_context():
            self.assertEqual(FamilyMember.query.filter_by(user_id=uid("shared@t.com")).count(), 2)
        f = client(); post(f, "/family/login", {"email": "shared@t.com", "password": "familypw1"})
        page = f.get("/family/dashboard").data.decode()
        self.assertIn("Pat M1", page); self.assertIn("Pat M2", page)     # patient switcher
        # An outsider linked ONLY to patient 1 must never be shown patient 2 by passing someone else's link id
        p3 = client(); register_patient(p3, "Pat M3", "pm3@t.com")
        self._add_family(p3, "Outsider", "outsider@t.com", "Cousin", ["view_vitals", "view_health_score"])
        with APP.app_context():
            others_link = FamilyMember.query.filter_by(user_id=uid("shared@t.com"), patient_id=uid("pm2@t.com")).first().id
        o = client(); post(o, "/family/login", {"email": "outsider@t.com", "password": "familypw1"})
        for url in ["/family/dashboard", "/family/vitals", "/family/health", "/family/updates"]:
            body = o.get(f"{url}?fm={others_link}").data.decode()
            self.assertNotIn("Pat M2", body, url)                          # foreign link id is ignored, never honoured
            self.assertNotIn("Pat M1", body, url)
            self.assertIn("Pat M3", body, url)                             # falls back to the outsider's OWN patient
        # and the strict helper itself refuses a foreign link
        from ecosystem.access import family_link_or_403
        from werkzeug.exceptions import Forbidden
        from flask_login import login_user
        with APP.test_request_context("/family/dashboard"):
            login_user(db.session.get(User, uid("outsider@t.com")))
            with self.assertRaises(Forbidden):
                family_link_or_403(others_link)

    # ---------------- emergency ----------------
    def test_70_emergency_fanout_uses_existing_engine(self):
        dc, pc, _ = self._connected_pair("Dr Emerg", "emerg@t.com", "LIC-EM", "Pat Emerg", "pem@t.com")
        stranger = self._verified_doctor("Dr Stranger", "stranger@t.com", "LIC-STR")
        self._add_family(pc, "Dad Em", "dadem@t.com", "Father", ["emergency_alerts"])
        self._add_family(pc, "Mum Em", "mumem@t.com", "Mother", ["view_vitals"])          # NO emergency permission
        with APP.app_context():
            for e in Notification.query.all():
                pass
        r = pc.post("/data-entry", data={"systolic_bp": 120, "diastolic_bp": 80, "heart_rate": 74, "oxygen_saturation": 87})
        self.assertEqual(r.status_code, 302)
        with APP.app_context():
            ev = EmergencyEvent.query.filter_by(patient_id=uid("pem@t.com")).all()
            self.assertEqual(len(ev), 1)
            self.assertIn("87", ev[0].details)
            for email, expect in [("pem@t.com", 1), ("emerg@t.com", 1), ("dadem@t.com", 1),
                                  ("mumem@t.com", 0), ("stranger@t.com", 0)]:
                n = Notification.query.filter_by(user_id=uid(email), notification_type="EMERGENCY").count()
                self.assertEqual(n, expect, email)
            msg = Notification.query.filter_by(user_id=uid("emerg@t.com"), notification_type="EMERGENCY").first().message
            self.assertIn("not a diagnosis", msg)
        # views
        self.assertIn(b"87", dc.get("/doctor/alerts").data)
        self.assertNotIn(b"Pat Emerg", stranger.get("/doctor/alerts").data)
        dad = client(); post(dad, "/family/login", {"email": "dadem@t.com", "password": "familypw1"})
        self.assertIn(b"EMERGENCY ALERT", dad.get("/family/dashboard").data)
        mum = client(); post(mum, "/family/login", {"email": "mumem@t.com", "password": "familypw1"})
        self.assertNotIn(b"EMERGENCY ALERT", mum.get("/family/dashboard").data)
        self.assertEqual(mum.get("/family/alerts").status_code, 403)
        pe = pc.get("/emergency").data.decode()
        fam_card = pe.split("Family who receive alerts")[1].split("Alert history")[0]
        self.assertIn("Dr. Dr Emerg", pe); self.assertIn("Dad Em", fam_card); self.assertNotIn("Mum Em", fam_card)
        # original behaviour intact: patient still sees the original flash + dashboard alert box
        self.assertIn("High Risk Alert", pc.get("/dashboard").data.decode())
        # non-emergency vitals do NOT create an event
        pc.post("/data-entry", data={"systolic_bp": 120, "diastolic_bp": 80, "heart_rate": 74, "oxygen_saturation": 98})
        with APP.app_context():
            self.assertEqual(EmergencyEvent.query.filter_by(patient_id=uid("pem@t.com")).count(), 1)

    # ---------------- notifications ----------------
    def test_80_notifications_page_and_ownership(self):
        dc = self._verified_doctor("Dr Note", "note@t.com", "LIC-NOTE")
        pc = client(); register_patient(pc, "Pat Note", "pnote@t.com")
        post(pc, f"/doctors/{did('note@t.com')}/request")
        page = dc.get("/notifications").data.decode()
        self.assertIn("New patient connection request from Pat Note", page)
        with APP.app_context():
            nid = Notification.query.filter_by(user_id=uid("note@t.com")).first().id
        # another user cannot open/mark someone else's notification
        self.assertEqual(post(pc, f"/notifications/{nid}/open").status_code, 403)
        self.assertEqual(post(dc, f"/notifications/{nid}/open").status_code, 302)
        with APP.app_context():
            self.assertTrue(db.session.get(Notification, nid).is_read)
        post(dc, "/notifications/read-all")

    def test_81_account_password_change(self):
        pc = client(); register_patient(pc, "Pat Acct", "pacct@t.com")
        r = post(pc, "/account", {"current_password": "wrong", "new_password": "newpassword1", "confirm_password": "newpassword1"}, follow_redirects=True)
        self.assertIn(b"incorrect", r.data)
        post(pc, "/account", {"current_password": "patientpw1", "new_password": "newpassword1", "confirm_password": "newpassword1", "phone": "123"})
        c2 = client()
        self.assertEqual(c2.post("/login", data={"email": "pacct@t.com", "password": "newpassword1"}).status_code, 302)

    # ---------------- misc hardening ----------------
    def test_90_lab_upload_path_traversal_fixed(self):
        pc = client(); register_patient(pc, "Pat Trav", "ptrav@t.com")
        r = pc.post("/labs", data={"hba1c": "5.5", "report_file": (io.BytesIO(PDF), "../../evil.pdf")},
                    content_type="multipart/form-data")
        self.assertEqual(r.status_code, 302)
        with APP.app_context():
            lab = LabReport.query.filter_by(user_id=uid("ptrav@t.com")).first()
            self.assertNotIn("..", lab.file_path); self.assertNotIn("/", lab.file_path)
            lid = lab.id
        self.assertEqual(pc.get(f"/files/lab/{lid}").status_code, 200)        # owner can download own file
        other = client(); register_patient(other, "Pat Trav2", "ptrav2@t.com")
        self.assertEqual(other.get(f"/files/lab/{lid}").status_code, 403)

    def test_91_doctor_can_download_connected_patients_lab_file_only(self):
        dc, pc, _ = self._connected_pair("Dr Lab", "lab@t.com", "LIC-LAB", "Pat Lab", "plab@t.com")
        pc.post("/labs", data={"hba1c": "5.5", "report_file": (io.BytesIO(PDF), "labs.pdf")}, content_type="multipart/form-data")
        with APP.app_context():
            lid = LabReport.query.filter_by(user_id=uid("plab@t.com")).first().id
            self.assertGreaterEqual(Notification.query.filter_by(user_id=uid("lab@t.com"), notification_type="DOCUMENT").count(), 1)
        self.assertEqual(dc.get(f"/doctor/patient/{uid('plab@t.com')}/lab/{lid}/file").status_code, 200)
        stranger = self._verified_doctor("Dr Lab2", "lab2@t.com", "LIC-LAB2")
        self.assertEqual(stranger.get(f"/doctor/patient/{uid('plab@t.com')}/lab/{lid}/file").status_code, 403)

    def test_92_error_pages_have_no_stack_traces(self):
        c = client()
        r = c.get("/definitely-not-a-page")
        self.assertEqual(r.status_code, 404)
        self.assertNotIn(b"Traceback", r.data)
        self.assertIn(b"LifeTwin", r.data)

    def test_93_security_headers(self):
        pc = client(); register_patient(pc, "Pat Hdr", "phdr@t.com")
        r = pc.get("/notifications")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")
        self.assertEqual(r.headers["Cache-Control"], "no-store")

    def test_94_admin_cli(self):
        register_doctor(client(), "Dr Cli", "cli@t.com", "LIC-CLI")
        runner = APP.test_cli_runner()
        out = runner.invoke(args=["doctor-verify", "cli@t.com"])
        self.assertEqual(out.exit_code, 0, out.output)
        self.assertIn("VERIFIED", out.output)
        out = runner.invoke(args=["doctor-list"])
        self.assertIn("cli@t.com", out.output)
        out = runner.invoke(args=["doctor-verify", "nobody@t.com"])
        self.assertNotEqual(out.exit_code, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
