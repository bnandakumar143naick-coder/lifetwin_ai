# LifeTwin AI

**Building a Digital Health Twin that predicts future health risks before they become diseases.**

LifeTwin AI is an AI-powered preventive healthcare platform. Users manually enter their health
information (no wearables required), and the platform generates health scores, symptom analysis,
future disease risk predictions, and a personalized prevention plan — all with explainable reasons.

## Features (MVP scope)

1. User Registration & Login
2. Health Profile Creation (lifestyle, medical history, family history)
3. Manual Health Data Entry (vitals: BP, blood sugar, heart rate, SpO2, temperature, cholesterol)
4. Optional Laboratory Report entry (HbA1c, lipid panel, liver/kidney markers)
5. Current Symptom logging
6. AI Health Analysis — Overall / Physical / Nutrition / Sleep / Hydration / Mental scores, each explained
7. Symptom Analysis — possible conditions, risk level, and advice
8. Future Disease Risk Prediction — current vs. 5-year risk for 10 conditions, with reasons
9. Personalized Prevention Plan — diet, exercise, lifestyle, and preventive-care guidance
10. Emergency Detection — flags dangerous vital values immediately
11. Health Dashboard — all of the above in one place, with monthly progress charts
12. AI Health Coach — chat interface that answers questions using the user's own data
13. Downloadable PDF Health Report

## Tech Stack

- **Backend:** Flask (Python)
- **Database:** SQLite (file-based, zero config)
- **Frontend:** Server-rendered HTML/CSS/JS + Chart.js for charts
- **PDF Generation:** ReportLab
- **AI Logic:** Rule-based, explainable scoring engine in `ai_engine.py` (no external API calls —
  works fully offline, which matters for rural/low-connectivity users)

## Setup

```bash
# 1. Create and activate a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app (this also initializes the SQLite database automatically)
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

## Project Structure

```
lifetwin_ai/
├── app.py                 # Flask routes / application entry point
├── database.py             # SQLite schema + connection helper
├── ai_engine.py             # Rule-based AI: scoring, symptom analysis, risk prediction, plans
├── pdf_generator.py         # PDF health report builder (ReportLab)
├── requirements.txt
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── register.html
│   ├── login.html
│   ├── profile.html
│   ├── data_entry.html
│   ├── lab_reports.html
│   ├── symptoms.html
│   ├── dashboard.html
│   └── coach.html
├── static/
│   └── css/style.css
└── instance/
    └── lifetwin.db          # created automatically on first run
```

## Notes

- All AI logic is **explainable by design**: every score and risk prediction comes with a list of
  the specific factors that produced it (e.g. "BMI 27.4 indicates overweight", "Elevated blood
  sugar reading"). This satisfies the project's Explainable AI requirement without needing a
  trained ML model or internet access.
- The disease risk model is a transparent, weighted risk-factor scoring system (squashed through a
  logistic curve to produce a 0-95% "risk-like" percentage) — it is intentionally simple and
  auditable rather than a black-box classifier, which is appropriate for a hackathon MVP and for
  explaining "why" to non-technical users.
- This is a wellness/education tool, **not a diagnostic medical device**. The app and PDF report
  both carry a disclaimer to that effect.

## Future Scope

- OCR to auto-read lab reports
- Doctor dashboard / hospital integration
- Multi-language support
- Voice-based AI assistant
- Cloud-based health records
- Swap the rule-based engine for a trained scikit-learn model once real training data is available
