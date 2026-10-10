# 🩺 LifeTwin AI

**Building a Digital Health Twin that predicts future health risks before they become diseases.**

A preventive healthcare platform that works entirely with **manually entered health data** —
no smartwatch or wearable required. Built for hackathon MVP scope, designed to be practical
for both urban and rural users.

---

## 🚀 Quick Start

```bash
# 1. Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
python app.py
```

Open **http://localhost:5000** in your browser.

The SQLite database and generated PDF reports are created automatically inside `instance/`
the first time you run the app — no manual DB setup needed.

---

## 📁 Folder Structure

```
lifetwin_ai/
│
├── app.py                     # Main Flask app — all routes
├── config.py                  # App configuration
├── models.py                  # SQLAlchemy models (User, HealthProfile, VitalSigns, LabReport, SymptomLog, HealthScoreHistory)
├── requirements.txt
│
├── utils/                     # The "AI" engine — explainable, rule-based
│   ├── health_score.py        # Module 6  — Health scoring (fitness/nutrition/sleep/hydration/mental)
│   ├── symptom_analyzer.py    # Module 7  — Symptom analysis
│   ├── risk_predictor.py      # Module 8  — Future disease risk prediction
│   ├── plan_generator.py      # Module 9  — Diet / exercise / lifestyle / preventive care plans
│   ├── emergency.py           # Module 10 — Emergency vital-sign detection
│   ├── health_coach.py        # Module 12 — AI Health Coach (Q&A grounded in user data)
│   └── pdf_report.py          # Module 13 — PDF report generation
│
├── templates/                 # Jinja2 HTML templates
│   ├── base.html               (navbar, flash messages, footer)
│   ├── index.html              (landing page)
│   ├── register.html / login.html
│   ├── profile.html            (Module 2 — Health Profile)
│   ├── data_entry.html         (Module 3 — Vital signs)
│   ├── labs.html                (Module 4 — Lab reports)
│   ├── symptoms.html            (Module 5 — Symptom selection)
│   ├── dashboard.html           (Module 11 — Health Dashboard, scores, charts, risks, plans)
│   └── coach.html               (Module 12 — AI Health Coach chat)
│
├── static/
│   ├── css/style.css
│   └── js/                     (Chart.js loaded via CDN in base.html)
│
└── instance/                   # Auto-created at runtime
    ├── lifetwin.db              (SQLite database)
    ├── uploads/                 (uploaded lab report files)
    └── reports/                 (generated PDF health reports)
```

---

## ✅ MVP Feature Coverage

| Spec Module | Status |
|---|---|
| 1. User Registration | ✅ `/register` |
| 2. Health Profile Creation (incl. auto BMI) | ✅ `/profile` |
| 3. Manual Vital Signs Entry | ✅ `/data-entry` |
| 4. Lab Reports (manual entry + optional file upload) | ✅ `/labs` |
| 5. Symptom Selection | ✅ `/symptoms` |
| 6. AI Health Score (5 sub-scores, explainable) | ✅ `utils/health_score.py` |
| 7. Symptom Analysis (possible conditions, risk level, advice) | ✅ `utils/symptom_analyzer.py` |
| 8. Future Disease Risk Prediction (10 diseases, current vs. future %, reasons) | ✅ `utils/risk_predictor.py` |
| 9. Personalized Prevention Plan (diet/exercise/lifestyle/preventive care) | ✅ `utils/plan_generator.py` |
| 10. Emergency Detection & Alerts | ✅ `utils/emergency.py` |
| 11. Health Dashboard (scores, charts, risks, plans in one place) | ✅ `/dashboard` |
| 12. AI Health Coach (Q&A grounded in user data) | ✅ `/coach` |
| 13. Downloadable PDF Health Report | ✅ `/report/download` |

---

## 🧠 How the "AI" Works (Explainable AI approach)

Rather than a black-box ML model (which would need large labeled medical datasets you
won't have for a hackathon), every module uses **transparent, weighted rule-based logic**:

- Each score/risk is built from clearly named factors (BMI, blood pressure, family history,
  lab values, lifestyle habits, etc.)
- Every result comes with a **list of reasons** — satisfying the "Explainable AI" claim in
  the pitch (Section 19) without requiring model training.
- This is easy to demo, easy to explain to judges, and 100% reproducible.

**Upgrade path:** once you have real (even synthetic) labeled data, you can swap
`utils/risk_predictor.py`'s scoring functions for a trained Scikit-learn model
(e.g. `RandomForestClassifier`) without changing any routes or templates — the
function signatures already return `(current_risk, future_risk, reasons)`.

---

## 🔭 Future Scope (post-hackathon, not built here)

- OCR to auto-read lab report PDFs/images (currently: manual entry + file upload for records)
- Doctor dashboard & hospital integration
- Multi-language support (important for rural reach)
- Voice-based AI assistant
- Cloud-based health records
- Smartwatch/wearable integration (optional add-on, not required)

---

## ⚠️ Disclaimer

LifeTwin AI provides AI-generated wellness insights for **preventive awareness only**.
It is **not a substitute for professional medical diagnosis or treatment**. This is reflected
in the UI (symptom analysis always says "not a diagnosis") and in every generated PDF report.


---

# 👨‍⚕️ Patient + Doctor + Family Ecosystem (extension)

LifeTwin AI is now a connected **Patient · Doctor · Family** platform. The original patient app, rule-based
engines (`utils/`), PDF report and database are unchanged in behaviour; everything new is **added alongside**.

## Run
```bash
pip install -r requirements.txt
python app.py                      # http://127.0.0.1:5000  (debugger OFF by default)
python seed_demo.py                # optional demo patient/doctor/family
python -m unittest tests.test_ecosystem -v   # 26 automated tests
```
Existing databases upgrade automatically on startup (`users.role`, `users.phone` are added; old users become PATIENT).

Environment variables: `SECRET_KEY` (**set this in production**), `DATABASE_URL`, `LIFETWIN_DEBUG=1` (dev only),
`LIFETWIN_HOST`, `PORT`, `LIFETWIN_AUTO_VERIFY_DOCTORS=1` (demo: new doctors are VERIFIED immediately).

## Logins
| Role | Register | Login |
|---|---|---|
| Patient | `/register` | `/login` |
| Doctor | `/doctor/register` | `/doctor/login` |
| Family | created by the patient at **Family** | `/family/login` |

## Doctor verification (application-level only — NOT an external licence check)
New doctors are `PENDING` and are hidden from patient search and cannot access data until verified:
```bash
flask --app app doctor-list
flask --app app doctor-verify  doctor@example.com
flask --app app doctor-reject  doctor@example.com     # also revokes data access
```

## How access control works
* Doctor → patient data only if doctor is `VERIFIED` **and** the connection is `ACCEPTED` (checked server-side on every request).
* Family → only their linked patient and only the flags the patient ticked (`FamilyPermission`); templates only receive permitted data.
* Unauthorized and non-existent targets both return **403** so IDs can't be enumerated.
* New POST routes use CSRF tokens; attachments live outside `static/`, have random names, are type/size/magic-byte checked and are served only to conversation participants.

## Emergency alerts
Detection is still `utils/emergency.py`. When it fires, an `EmergencyEvent` and in-app notifications are created for the
patient, ACCEPTED doctors and family with `emergency_alerts`. No SMS/e-mail/emergency-service contact is made.

## Known limitations
In-app notifications only (no e-mail/SMS/push) · chat uses 10-second HTTP polling (no WebSockets, no online indicator) ·
legacy patient forms still have no CSRF tokens · no login rate-limiting · no admin web UI (CLI only) · SQLite default ·
weight history starts from the first profile save after upgrade · outputs are informational, not medical advice.
