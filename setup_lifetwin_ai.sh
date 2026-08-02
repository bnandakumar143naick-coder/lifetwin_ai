#!/bin/bash
# LifeTwin AI - automated project setup script
# Usage: bash setup_lifetwin_ai.sh
set -e

echo "Creating LifeTwin AI project structure..."

mkdir -p "lifetwin_ai/instance"
mkdir -p "lifetwin_ai/static/css"
mkdir -p "lifetwin_ai/templates"

cat << 'LIFETWIN_EOF' > "lifetwin_ai/README.md"
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
LIFETWIN_EOF

cat << 'LIFETWIN_EOF' > "lifetwin_ai/ai_engine.py"
"""
ai_engine.py - Rule-based / explainable "AI" engine for LifeTwin AI.

All logic here is intentionally explainable (each output includes the
reasons behind it) so users can understand *why* a score or prediction
was produced, per the "Explainable AI" project requirement.
"""
import math


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def compute_bmi(weight_kg, height_cm):
    if not weight_kg or not height_cm:
        return None
    height_m = height_cm / 100.0
    if height_m <= 0:
        return None
    return round(weight_kg / (height_m ** 2), 1)


def bmi_category(bmi):
    if bmi is None:
        return "Unknown"
    if bmi < 18.5:
        return "Underweight"
    if bmi < 25:
        return "Normal"
    if bmi < 30:
        return "Overweight"
    return "Obese"


SMOKING_SCORE = {"never": 0, "former": 10, "occasional": 25, "regular": 45}
ALCOHOL_SCORE = {"never": 0, "occasional": 8, "moderate": 18, "heavy": 40}
EXERCISE_SCORE = {"none": 40, "rarely": 25, "1-2 times/week": 12, "3-4 times/week": 4, "daily": 0}
STRESS_SCORE = {"low": 0, "moderate": 15, "high": 35, "severe": 50}


# ---------------------------------------------------------------------------
# Module 6: AI Health Analysis (scores)
# ---------------------------------------------------------------------------

def compute_health_scores(profile, latest_vitals):
    """
    Returns dict with overall + sub-scores (0-100) and explanations.
    profile: sqlite Row / dict of profile fields
    latest_vitals: sqlite Row / dict or None
    """
    reasons = {"physical": [], "nutrition": [], "sleep": [], "hydration": [], "mental": []}

    # --- Physical Fitness Score ---
    physical = 100
    bmi = compute_bmi(profile.get("weight_kg"), profile.get("height_cm"))
    if bmi is not None:
        if bmi < 18.5:
            physical -= 15
            reasons["physical"].append(f"BMI {bmi} indicates you are underweight.")
        elif bmi >= 30:
            physical -= 35
            reasons["physical"].append(f"BMI {bmi} indicates obesity, raising physical strain.")
        elif bmi >= 25:
            physical -= 18
            reasons["physical"].append(f"BMI {bmi} indicates you are overweight.")
        else:
            reasons["physical"].append(f"BMI {bmi} is in the healthy range.")

    exercise = (profile.get("exercise_freq") or "rarely").lower()
    ex_penalty = EXERCISE_SCORE.get(exercise, 25)
    physical -= ex_penalty
    if ex_penalty > 10:
        reasons["physical"].append(f"Low exercise frequency ('{exercise}') is reducing your fitness score.")
    else:
        reasons["physical"].append(f"Exercise frequency ('{exercise}') is helping your fitness score.")

    smoking = (profile.get("smoking") or "never").lower()
    physical -= SMOKING_SCORE.get(smoking, 20)
    if smoking not in ("never", "former"):
        reasons["physical"].append("Smoking habit is significantly lowering physical health.")

    if latest_vitals:
        hr = latest_vitals.get("heart_rate")
        if hr and (hr < 50 or hr > 100):
            physical -= 10
            reasons["physical"].append(f"Heart rate of {hr} bpm is outside the normal resting range (60-100).")
        spo2 = latest_vitals.get("spo2")
        if spo2 and spo2 < 95:
            physical -= 15
            reasons["physical"].append(f"Oxygen saturation of {spo2}% is below the healthy threshold (95%+).")

    physical = clamp(round(physical))

    # --- Nutrition Score ---
    nutrition = 100
    if bmi is not None and (bmi < 18.5 or bmi >= 30):
        nutrition -= 20
        reasons["nutrition"].append("BMI outside normal range suggests dietary imbalance.")
    if latest_vitals and latest_vitals.get("blood_sugar"):
        bs = latest_vitals["blood_sugar"]
        if bs >= 126:
            nutrition -= 30
            reasons["nutrition"].append(f"Fasting blood sugar of {bs} mg/dL is in the diabetic range.")
        elif bs >= 100:
            nutrition -= 15
            reasons["nutrition"].append(f"Blood sugar of {bs} mg/dL is in the pre-diabetic range.")
        else:
            reasons["nutrition"].append(f"Blood sugar of {bs} mg/dL is within normal range.")
    if latest_vitals and latest_vitals.get("cholesterol"):
        chol = latest_vitals["cholesterol"]
        if chol >= 240:
            nutrition -= 20
            reasons["nutrition"].append(f"Total cholesterol of {chol} mg/dL is high.")
        elif chol >= 200:
            nutrition -= 10
            reasons["nutrition"].append(f"Total cholesterol of {chol} mg/dL is borderline high.")
    nutrition = clamp(round(nutrition))

    # --- Sleep Quality Score ---
    sleep_hours = profile.get("sleep_hours")
    if sleep_hours is None:
        sleep = 60
        reasons["sleep"].append("No sleep data provided; using a default estimate.")
    else:
        if 7 <= sleep_hours <= 9:
            sleep = 100
            reasons["sleep"].append(f"{sleep_hours} hours of sleep is within the ideal 7-9 hour range.")
        elif 6 <= sleep_hours < 7 or 9 < sleep_hours <= 10:
            sleep = 75
            reasons["sleep"].append(f"{sleep_hours} hours of sleep is slightly outside the ideal range.")
        else:
            sleep = 45
            reasons["sleep"].append(f"{sleep_hours} hours of sleep is significantly outside the healthy range.")
    sleep = clamp(round(sleep))

    # --- Hydration Score ---
    water = profile.get("water_intake_l")
    if water is None:
        hydration = 60
        reasons["hydration"].append("No water intake data provided; using a default estimate.")
    else:
        if water >= 2.5:
            hydration = 100
            reasons["hydration"].append(f"Water intake of {water} L/day meets recommended levels.")
        elif water >= 1.5:
            hydration = 75
            reasons["hydration"].append(f"Water intake of {water} L/day is slightly below the recommended 2.5 L.")
        else:
            hydration = 45
            reasons["hydration"].append(f"Water intake of {water} L/day is well below the recommended level.")
    hydration = clamp(round(hydration))

    # --- Mental Wellness Score ---
    stress = (profile.get("stress_level") or "moderate").lower()
    mental = 100 - STRESS_SCORE.get(stress, 15)
    reasons["mental"].append(f"Stress level reported as '{stress}'.")
    if sleep_hours is not None and sleep_hours < 6:
        mental -= 10
        reasons["mental"].append("Insufficient sleep is also affecting mental wellness.")
    mental = clamp(round(mental))

    overall = clamp(round(0.30 * physical + 0.25 * nutrition + 0.20 * sleep + 0.10 * hydration + 0.15 * mental))

    return {
        "overall": overall,
        "physical": physical,
        "nutrition": nutrition,
        "sleep": sleep,
        "hydration": hydration,
        "mental": mental,
        "reasons": reasons,
        "bmi": bmi,
        "bmi_category": bmi_category(bmi),
    }


# ---------------------------------------------------------------------------
# Module 7: Symptom Analysis
# ---------------------------------------------------------------------------

SYMPTOM_CONDITION_MAP = {
    "Headache": [("Tension headache / dehydration", "Low"), ("Migraine", "Medium"), ("High blood pressure", "Medium")],
    "Fever": [("Common viral infection", "Low"), ("Bacterial infection", "Medium"), ("Flu", "Medium")],
    "Cough": [("Common cold", "Low"), ("Bronchitis", "Medium"), ("Respiratory infection", "Medium")],
    "Chest Pain": [("Muscle strain", "Low"), ("Acid reflux", "Medium"), ("Cardiac issue - needs urgent evaluation", "High")],
    "Stomach Pain": [("Indigestion", "Low"), ("Gastritis", "Medium"), ("Food poisoning", "Medium")],
    "Fatigue": [("Poor sleep/lifestyle", "Low"), ("Anemia", "Medium"), ("Thyroid imbalance", "Medium")],
    "Vomiting": [("Food intolerance", "Low"), ("Gastroenteritis", "Medium"), ("Food poisoning", "Medium")],
    "Tooth Pain": [("Dental cavity", "Low"), ("Gum infection", "Medium")],
    "Skin Rash": [("Allergic reaction", "Low"), ("Skin infection", "Medium")],
    "Dizziness": [("Dehydration", "Low"), ("Low blood pressure", "Medium"), ("Inner ear issue", "Medium")],
    "Shortness of Breath": [("Anxiety", "Low"), ("Asthma flare-up", "Medium"), ("Cardiac/respiratory emergency", "High")],
}

RISK_ORDER = {"Low": 0, "Medium": 1, "High": 2}


def analyze_symptoms(symptoms_list, profile, latest_vitals):
    """Returns list of {symptom, possible_conditions, risk_level, advice}."""
    results = []
    highest_risk = "Low"
    for symptom in symptoms_list:
        options = SYMPTOM_CONDITION_MAP.get(symptom, [("General health concern", "Low")])
        conditions = [c for c, _ in options]
        risk = max((r for _, r in options), key=lambda r: RISK_ORDER[r])

        # Escalate risk based on profile / vitals context
        if symptom == "Chest Pain" and profile.get("heart_disease"):
            risk = "High"
        if symptom == "Shortness of Breath" and (profile.get("asthma") or profile.get("heart_disease")):
            risk = "High"
        if symptom == "Headache" and latest_vitals and latest_vitals.get("systolic") and latest_vitals["systolic"] >= 160:
            risk = "High"
        if symptom == "Fatigue" and latest_vitals and latest_vitals.get("blood_sugar") and latest_vitals["blood_sugar"] >= 180:
            risk = "High"

        if RISK_ORDER[risk] > RISK_ORDER[highest_risk]:
            highest_risk = risk

        advice = "Monitor at home and rest."
        if risk == "Medium":
            advice = "Home care is reasonable, but consult a doctor if symptoms persist beyond 2-3 days or worsen."
        if risk == "High":
            advice = "Please consult a doctor promptly or seek immediate medical attention."

        results.append({
            "symptom": symptom,
            "possible_conditions": conditions,
            "risk_level": risk,
            "advice": advice,
        })

    return results, highest_risk


# ---------------------------------------------------------------------------
# Module 8: Future Disease Risk Prediction
# ---------------------------------------------------------------------------

def _risk_to_pct(score):
    """Convert a raw additive risk score into a bounded 0-95% probability-like value."""
    return round(clamp(100 / (1 + math.exp(-(score - 50) / 15)), 1, 95), 1)


def predict_disease_risks(profile, latest_vitals, latest_lab):
    """
    Returns dict: disease -> {current_risk, future_risk (in ~5 years), reasons}
    Simple, explainable additive risk-factor scoring (logistic-squashed).
    """
    bmi = compute_bmi(profile.get("weight_kg"), profile.get("height_cm"))
    age = profile.get("age") or 30
    smoking = (profile.get("smoking") or "never").lower()
    exercise = (profile.get("exercise_freq") or "rarely").lower()

    diseases = {}

    def build(name, base, factors, growth_per_year):
        score = base
        reasons = []
        for label, condition, weight in factors:
            if condition:
                score += weight
                reasons.append(label)
        current = _risk_to_pct(score)
        future_score = score + growth_per_year * 5
        future = _risk_to_pct(future_score)
        future = max(future, current)  # future risk never shown lower than current
        diseases[name] = {
            "current_risk": current,
            "future_risk": future,
            "reasons": reasons if reasons else ["No major risk factors identified."],
        }

    # Diabetes
    build("Diabetes", 20, [
        ("Family history of diabetes", profile.get("family_diabetes"), 20),
        ("Existing diabetes diagnosis", profile.get("diabetes"), 35),
        (f"BMI ({bmi}) indicates overweight/obesity", bmi and bmi >= 25, 15),
        ("Elevated blood sugar reading", latest_vitals and latest_vitals.get("blood_sugar") and latest_vitals["blood_sugar"] >= 100, 20),
        ("Elevated HbA1c", latest_lab and latest_lab.get("hba1c") and latest_lab["hba1c"] >= 5.7, 15),
        ("Low exercise frequency", exercise in ("none", "rarely"), 10),
        ("Age 45+", age >= 45, 10),
    ], growth_per_year=2.5)

    # Hypertension
    build("Hypertension", 15, [
        ("Existing hypertension diagnosis", profile.get("hypertension"), 30),
        ("Elevated blood pressure reading", latest_vitals and latest_vitals.get("systolic") and latest_vitals["systolic"] >= 130, 25),
        ("High stress level", (profile.get("stress_level") or "").lower() in ("high", "severe"), 15),
        ("Smoking habit", smoking in ("occasional", "regular"), 10),
        (f"BMI ({bmi}) indicates overweight/obesity", bmi and bmi >= 25, 10),
        ("High alcohol consumption", (profile.get("alcohol") or "").lower() == "heavy", 10),
        ("Age 45+", age >= 45, 10),
    ], growth_per_year=2.8)

    # Heart Disease
    build("Heart Disease", 10, [
        ("Existing heart disease diagnosis", profile.get("heart_disease"), 35),
        ("Family history of heart disease", profile.get("family_heart_disease"), 20),
        ("Smoking habit", smoking in ("occasional", "regular"), 20),
        ("High cholesterol reading", latest_vitals and latest_vitals.get("cholesterol") and latest_vitals["cholesterol"] >= 200, 15),
        ("Existing hypertension", profile.get("hypertension"), 15),
        ("Existing diabetes", profile.get("diabetes"), 15),
        ("Low exercise frequency", exercise in ("none", "rarely"), 10),
        ("Age 45+", age >= 45, 10),
    ], growth_per_year=2.3)

    # Stroke
    build("Stroke", 8, [
        ("Family history of stroke", profile.get("family_stroke"), 20),
        ("Existing hypertension", profile.get("hypertension"), 25),
        ("Smoking habit", smoking in ("occasional", "regular"), 15),
        ("Existing heart disease", profile.get("heart_disease"), 15),
        ("Existing diabetes", profile.get("diabetes"), 10),
        ("Age 55+", age >= 55, 15),
    ], growth_per_year=2.0)

    # Kidney Disease
    build("Kidney Disease", 8, [
        ("Existing kidney disease diagnosis", profile.get("kidney_disease"), 35),
        ("Family history of kidney disease", profile.get("family_kidney_disease"), 15),
        ("Existing diabetes", profile.get("diabetes"), 20),
        ("Existing hypertension", profile.get("hypertension"), 15),
        ("Elevated creatinine", latest_lab and latest_lab.get("creatinine") and latest_lab["creatinine"] > 1.3, 20),
        ("Low eGFR", latest_lab and latest_lab.get("kidney_egfr") and latest_lab["kidney_egfr"] < 60, 20),
    ], growth_per_year=1.8)

    # Fatty Liver Disease
    build("Fatty Liver Disease", 10, [
        (f"BMI ({bmi}) indicates overweight/obesity", bmi and bmi >= 25, 20),
        ("High alcohol consumption", (profile.get("alcohol") or "").lower() in ("moderate", "heavy"), 20),
        ("Existing diabetes", profile.get("diabetes"), 15),
        ("Elevated liver enzymes (ALT)", latest_lab and latest_lab.get("liver_alt") and latest_lab["liver_alt"] > 40, 20),
        ("Low exercise frequency", exercise in ("none", "rarely"), 10),
    ], growth_per_year=1.8)

    # Obesity
    build("Obesity", 5, [
        (f"Current BMI ({bmi}) already overweight", bmi and 25 <= bmi < 30, 25),
        (f"Current BMI ({bmi}) already obese", bmi and bmi >= 30, 45),
        ("Low exercise frequency", exercise in ("none", "rarely"), 15),
        ("High stress level", (profile.get("stress_level") or "").lower() in ("high", "severe"), 10),
    ], growth_per_year=1.5)

    # High Cholesterol
    build("High Cholesterol", 12, [
        ("Elevated cholesterol reading", latest_vitals and latest_vitals.get("cholesterol") and latest_vitals["cholesterol"] >= 200, 30),
        ("Elevated lab cholesterol", latest_lab and latest_lab.get("lab_cholesterol") and latest_lab["lab_cholesterol"] >= 200, 25),
        (f"BMI ({bmi}) indicates overweight/obesity", bmi and bmi >= 25, 15),
        ("Low exercise frequency", exercise in ("none", "rarely"), 10),
        ("Smoking habit", smoking in ("occasional", "regular"), 10),
    ], growth_per_year=2.0)

    # Thyroid Disorders
    build("Thyroid Disorders", 10, [
        ("Existing thyroid disease diagnosis", profile.get("thyroid_disease"), 40),
        ("Female gender (higher baseline prevalence)", (profile.get("gender") or "").lower() == "female", 8),
        ("Age 40+", age >= 40, 8),
    ], growth_per_year=1.2)

    # Arthritis
    build("Arthritis", 8, [
        (f"BMI ({bmi}) adds joint stress", bmi and bmi >= 27, 15),
        ("Age 50+", age >= 50, 25),
        ("Sedentary lifestyle", exercise in ("none", "rarely"), 10),
    ], growth_per_year=2.2)

    return diseases


# ---------------------------------------------------------------------------
# Module 9: Personalized Prevention Plan
# ---------------------------------------------------------------------------

def generate_prevention_plan(profile, disease_risks):
    bmi = compute_bmi(profile.get("weight_kg"), profile.get("height_cm"))
    high_risk_diseases = [d for d, v in disease_risks.items() if v["future_risk"] >= 50]

    diet = {
        "breakfast": ["Oats or whole-grain cereal", "Boiled eggs or a handful of soaked nuts", "Fresh seasonal fruit"],
        "lunch": ["Brown rice or whole-wheat roti", "Dal/legumes or lean protein", "A large portion of mixed vegetables", "Curd/yogurt"],
        "dinner": ["Light whole-grain meal", "Steamed/grilled vegetables", "Soup or salad"],
        "snacks": ["Fruits", "Roasted chana or nuts", "Buttermilk / green tea"],
        "water_target_l": max(2.5, round((profile.get("weight_kg") or 60) * 0.033, 1)),
        "foods_to_avoid": ["Fried and oily food", "Sugary drinks and desserts", "Excess salt / processed food"],
    }

    if profile.get("diabetes") or "Diabetes" in high_risk_diseases:
        diet["foods_to_avoid"].append("Refined sugar, white rice, and sweetened beverages")
        diet["breakfast"].append("Prefer low-glycemic-index foods")
    if profile.get("hypertension") or "Hypertension" in high_risk_diseases:
        diet["foods_to_avoid"].append("High-sodium/pickled/processed foods")
    if bmi and bmi >= 25:
        diet["foods_to_avoid"].append("High-calorie fast food and sugary snacks")

    exercise_freq = (profile.get("exercise_freq") or "rarely").lower()
    if exercise_freq in ("none", "rarely"):
        exercise_level = "Beginner"
        weekly = {
            "Mon": "20 min brisk walking",
            "Tue": "15 min stretching/yoga",
            "Wed": "20 min brisk walking",
            "Thu": "Rest / light stretching",
            "Fri": "20 min brisk walking",
            "Sat": "25 min yoga",
            "Sun": "Rest",
        }
    elif exercise_freq in ("1-2 times/week",):
        exercise_level = "Intermediate"
        weekly = {
            "Mon": "30 min brisk walking / cycling",
            "Tue": "20 min strength/bodyweight training",
            "Wed": "30 min yoga",
            "Thu": "Rest",
            "Fri": "30 min brisk walking / cycling",
            "Sat": "20 min strength training",
            "Sun": "Light stretching",
        }
    else:
        exercise_level = "Advanced"
        weekly = {
            "Mon": "40 min cardio / gym",
            "Tue": "30 min strength training",
            "Wed": "30 min yoga / mobility",
            "Thu": "40 min cardio / gym",
            "Fri": "30 min strength training",
            "Sat": "45 min mixed workout",
            "Sun": "Active recovery / stretching",
        }

    exercise_plan = {"level": exercise_level, "weekly_schedule": weekly}

    lifestyle = {
        "sleep_schedule": "Aim for 7-9 hours of consistent sleep; sleep and wake at the same time daily.",
        "stress_management": "Practice 10 minutes of deep breathing or meditation daily.",
        "weight_management": (
            "Maintain current healthy weight through balanced diet and regular activity."
            if bmi and 18.5 <= bmi < 25
            else "Focus on gradual, sustainable weight change through diet and exercise; consult a nutritionist if needed."
        ),
        "daily_goals": [
            f"Drink at least {diet['water_target_l']} L of water",
            "Take a 10,000-step walk or equivalent activity",
            "Limit screen time before bed",
        ],
    }

    preventive_care = {
        "checkup_reminder": "Schedule a general health check-up every 6 months.",
        "medication_reminder": "Take prescribed medications on time; do not skip doses." if profile.get("current_medications") else "No current medications on file.",
        "vaccination_reminder": "Ensure annual flu vaccination and any age-appropriate vaccines are up to date.",
    }

    if high_risk_diseases:
        preventive_care["priority_screenings"] = [
            f"Screen for {d} given elevated 5-year risk ({disease_risks[d]['future_risk']}%)." for d in high_risk_diseases
        ]

    return {"diet": diet, "exercise": exercise_plan, "lifestyle": lifestyle, "preventive_care": preventive_care}


# ---------------------------------------------------------------------------
# Module 10: Emergency Detection
# ---------------------------------------------------------------------------

def check_emergency(latest_vitals):
    alerts = []
    if not latest_vitals:
        return alerts
    systolic = latest_vitals.get("systolic")
    diastolic = latest_vitals.get("diastolic")
    blood_sugar = latest_vitals.get("blood_sugar")
    spo2 = latest_vitals.get("spo2")
    heart_rate = latest_vitals.get("heart_rate")
    temperature = latest_vitals.get("temperature")

    if systolic and systolic >= 180:
        alerts.append(f"Extremely high blood pressure detected (Systolic {systolic} mmHg). This is a hypertensive crisis.")
    elif diastolic and diastolic >= 120:
        alerts.append(f"Extremely high diastolic blood pressure detected ({diastolic} mmHg).")
    if blood_sugar and blood_sugar >= 300:
        alerts.append(f"Very high blood sugar detected ({blood_sugar} mg/dL). Risk of hyperglycemic emergency.")
    if blood_sugar and blood_sugar <= 60:
        alerts.append(f"Very low blood sugar detected ({blood_sugar} mg/dL). Risk of hypoglycemia.")
    if spo2 and spo2 < 90:
        alerts.append(f"Very low oxygen saturation detected ({spo2}%). This requires immediate medical attention.")
    if heart_rate and heart_rate > 130:
        alerts.append(f"Very high heart rate detected ({heart_rate} bpm).")
    if heart_rate and heart_rate < 40:
        alerts.append(f"Very low heart rate detected ({heart_rate} bpm).")
    if temperature and temperature >= 103:
        alerts.append(f"Very high body temperature detected ({temperature} degrees F). Risk of high fever complications.")

    return alerts


# ---------------------------------------------------------------------------
# Module 12: AI Health Coach (rule-based Q&A)
# ---------------------------------------------------------------------------

def ai_coach_answer(question, profile, latest_vitals, scores, disease_risks):
    q = (question or "").lower()

    if "blood pressure" in q:
        if latest_vitals and latest_vitals.get("systolic"):
            sys_, dia_ = latest_vitals["systolic"], latest_vitals.get("diastolic")
            if sys_ >= 130:
                return (f"Your latest reading is {sys_}/{dia_} mmHg, which is elevated. Contributing factors may "
                        f"include stress level ('{profile.get('stress_level')}'), sodium intake, low exercise, "
                        f"or family/medical history. Consider reducing salt, increasing activity, and managing stress.")
            return f"Your latest blood pressure reading is {sys_}/{dia_} mmHg, which is within a healthy range. Keep it up!"
        return "I don't have a recent blood pressure reading. Please log your vitals so I can analyze this for you."

    if "what should i eat" in q or "diet" in q or "eat today" in q:
        return ("Based on your profile, focus on whole grains, vegetables, lean protein, and plenty of water. "
                "Avoid fried, sugary, and high-sodium foods. Check your Prevention Plan tab for a full daily meal plan.")

    if "cholesterol" in q:
        chol = latest_vitals.get("cholesterol") if latest_vitals else None
        if chol:
            if chol >= 200:
                return (f"Your latest cholesterol reading is {chol} mg/dL, which is elevated. Reduce fried/fatty foods, "
                        f"increase fiber intake, and add regular cardio exercise. Consider consulting a doctor for a lipid panel.")
            return f"Your latest cholesterol reading is {chol} mg/dL, which is within a healthy range."
        return "I don't have a recent cholesterol reading. Please add it under Health Data Entry or Lab Reports."

    if "health score" in q or "score decreasing" in q or "why is my health" in q:
        reasons = []
        for k in ("physical", "nutrition", "sleep", "hydration", "mental"):
            reasons.extend(scores.get("reasons", {}).get(k, [])[:1])
        if reasons:
            return "Your score is influenced by: " + " ".join(reasons)
        return "Log more health data (vitals, sleep, water intake) so I can give you a detailed explanation."

    if "exercise" in q or "workout" in q:
        freq = (profile.get("exercise_freq") or "rarely")
        return (f"Your current exercise frequency is '{freq}'. Based on your profile, I recommend starting with brisk "
                f"walking and light yoga, then progressing to strength training. See the Prevention Plan tab for your "
                f"full weekly schedule.")

    if "diabetes" in q:
        risk = disease_risks.get("Diabetes") if disease_risks else None
        if risk:
            return (f"Your estimated future diabetes risk is {risk['future_risk']}%, based on: {', '.join(risk['reasons'])}. "
                     f"Maintaining a healthy weight, exercising regularly, and reducing sugar intake can lower this risk.")
        return "Please complete your health profile so I can estimate your diabetes risk."

    if "sleep" in q:
        hrs = profile.get("sleep_hours")
        if hrs:
            return f"You reported {hrs} hours of sleep. Adults should aim for 7-9 hours nightly for optimal recovery and mental wellness."
        return "Please log your average sleep hours in your Health Profile so I can assess your sleep quality."

    if "water" in q or "hydration" in q:
        water = profile.get("water_intake_l")
        return (f"You reported {water} L/day of water intake." if water else "No hydration data on file.") + \
               " The general recommendation is at least 2.5-3 L of water per day, adjusted for body weight and activity."

    return ("I can help explain your blood pressure, cholesterol, diabetes risk, diet, exercise, sleep, hydration, "
            "or health score. Try asking, for example: 'Why is my blood pressure high?' or 'What should I eat today?'")
LIFETWIN_EOF

cat << 'LIFETWIN_EOF' > "lifetwin_ai/app.py"
"""
app.py - LifeTwin AI main Flask application.

Run with:  python app.py
Then open: http://127.0.0.1:5000
"""
import os
from functools import wraps

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
LIFETWIN_EOF

cat << 'LIFETWIN_EOF' > "lifetwin_ai/database.py"
"""
database.py - SQLite database connection and schema initialization for LifeTwin AI
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "lifetwin.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    age INTEGER,
    gender TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    height_cm REAL,
    weight_kg REAL,
    smoking TEXT,
    alcohol TEXT,
    exercise_freq TEXT,
    sleep_hours REAL,
    water_intake_l REAL,
    stress_level TEXT,
    occupation TEXT,
    diabetes INTEGER DEFAULT 0,
    hypertension INTEGER DEFAULT 0,
    heart_disease INTEGER DEFAULT 0,
    kidney_disease INTEGER DEFAULT 0,
    asthma INTEGER DEFAULT 0,
    thyroid_disease INTEGER DEFAULT 0,
    allergies TEXT,
    current_medications TEXT,
    family_diabetes INTEGER DEFAULT 0,
    family_heart_disease INTEGER DEFAULT 0,
    family_stroke INTEGER DEFAULT 0,
    family_cancer INTEGER DEFAULT 0,
    family_kidney_disease INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS vitals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    systolic REAL,
    diastolic REAL,
    blood_sugar REAL,
    heart_rate REAL,
    spo2 REAL,
    temperature REAL,
    cholesterol REAL,
    recorded_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lab_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    hba1c REAL,
    lab_cholesterol REAL,
    hemoglobin REAL,
    creatinine REAL,
    liver_alt REAL,
    liver_ast REAL,
    kidney_egfr REAL,
    recorded_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS symptoms_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    symptoms_csv TEXT,
    recorded_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS health_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    overall REAL,
    physical REAL,
    nutrition REAL,
    sleep REAL,
    hydration REAL,
    mental REAL,
    computed_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized at", DB_PATH)
LIFETWIN_EOF

cat << 'LIFETWIN_EOF' > "lifetwin_ai/pdf_generator.py"
"""
pdf_generator.py - Generates a downloadable PDF Health Report (Module 13)
"""
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)


def build_health_report_pdf(user, profile, latest_vitals, scores, symptom_results,
                             disease_risks, plan, alerts):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                             topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                             leftMargin=1.8 * cm, rightMargin=1.8 * cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCustom", parent=styles["Title"], textColor=colors.HexColor("#0f6e5b"))
    h2 = ParagraphStyle("H2Custom", parent=styles["Heading2"], textColor=colors.HexColor("#0f6e5b"),
                         spaceBefore=14, spaceAfter=6)
    normal = styles["Normal"]
    small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=9, textColor=colors.grey)

    story = []
    story.append(Paragraph("LifeTwin AI — Digital Health Twin Report", title_style))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%d %B %Y, %H:%M')}", small))
    story.append(Spacer(1, 0.5 * cm))

    # Personal Information
    story.append(Paragraph("Personal Information", h2))
    personal_data = [
        ["Full Name", user["full_name"]],
        ["Email", user["email"]],
        ["Age", str(user["age"] or "-")],
        ["Gender", user["gender"] or "-"],
        ["Height (cm)", str(profile.get("height_cm") or "-")],
        ["Weight (kg)", str(profile.get("weight_kg") or "-")],
        ["BMI", f"{scores.get('bmi')} ({scores.get('bmi_category')})" if scores.get("bmi") else "-"],
    ]
    story.append(_table(personal_data, [5 * cm, 10 * cm]))

    # Emergency Alerts
    if alerts:
        story.append(Paragraph("Emergency Alerts", h2))
        for a in alerts:
            story.append(Paragraph(f"⚠ {a}", ParagraphStyle("Alert", parent=normal, textColor=colors.red)))

    # Health Scores
    story.append(Paragraph("Health Scores", h2))
    score_data = [["Metric", "Score (0-100)"]]
    for label, key in [("Overall Health", "overall"), ("Physical Fitness", "physical"),
                        ("Nutrition", "nutrition"), ("Sleep Quality", "sleep"),
                        ("Hydration", "hydration"), ("Mental Wellness", "mental")]:
        score_data.append([label, str(scores.get(key))])
    story.append(_table(score_data, [8 * cm, 7 * cm], header=True))

    # Latest Vitals
    story.append(Paragraph("Latest Vital Signs", h2))
    if latest_vitals:
        vit_data = [
            ["Blood Pressure", f"{latest_vitals.get('systolic', '-')}/{latest_vitals.get('diastolic', '-')} mmHg"],
            ["Blood Sugar", f"{latest_vitals.get('blood_sugar', '-')} mg/dL"],
            ["Heart Rate", f"{latest_vitals.get('heart_rate', '-')} bpm"],
            ["Oxygen Saturation", f"{latest_vitals.get('spo2', '-')} %"],
            ["Body Temperature", f"{latest_vitals.get('temperature', '-')} F"],
            ["Cholesterol", f"{latest_vitals.get('cholesterol', '-')} mg/dL"],
        ]
        story.append(_table(vit_data, [5 * cm, 10 * cm]))
    else:
        story.append(Paragraph("No vitals recorded yet.", normal))

    # Symptom Analysis
    story.append(Paragraph("Symptom Analysis", h2))
    if symptom_results:
        for s in symptom_results:
            story.append(Paragraph(f"<b>{s['symptom']}</b> — Risk: {s['risk_level']}", normal))
            story.append(Paragraph(f"Possible: {', '.join(s['possible_conditions'])}", small))
            story.append(Paragraph(f"Advice: {s['advice']}", small))
            story.append(Spacer(1, 0.15 * cm))
    else:
        story.append(Paragraph("No current symptoms reported.", normal))

    # Disease Risk Predictions
    story.append(PageBreak())
    story.append(Paragraph("Future Disease Risk Predictions", h2))
    risk_data = [["Condition", "Current Risk", "5-Year Risk"]]
    for disease, v in disease_risks.items():
        risk_data.append([disease, f"{v['current_risk']}%", f"{v['future_risk']}%"])
    story.append(_table(risk_data, [7 * cm, 4 * cm, 4 * cm], header=True))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Key contributing factors:", styles["Heading4"]))
    for disease, v in disease_risks.items():
        if v["future_risk"] >= 40:
            story.append(Paragraph(f"<b>{disease}:</b> {', '.join(v['reasons'])}", small))

    # Lifestyle Assessment
    story.append(Paragraph("Lifestyle Assessment", h2))
    lifestyle_data = [
        ["Smoking", profile.get("smoking") or "-"],
        ["Alcohol Consumption", profile.get("alcohol") or "-"],
        ["Exercise Frequency", profile.get("exercise_freq") or "-"],
        ["Sleep Hours", str(profile.get("sleep_hours") or "-")],
        ["Water Intake (L/day)", str(profile.get("water_intake_l") or "-")],
        ["Stress Level", profile.get("stress_level") or "-"],
        ["Occupation", profile.get("occupation") or "-"],
    ]
    story.append(_table(lifestyle_data, [5 * cm, 10 * cm]))

    # Diet Plan
    story.append(Paragraph("Personalized Diet Plan", h2))
    diet = plan["diet"]
    story.append(Paragraph(f"<b>Breakfast:</b> {', '.join(diet['breakfast'])}", normal))
    story.append(Paragraph(f"<b>Lunch:</b> {', '.join(diet['lunch'])}", normal))
    story.append(Paragraph(f"<b>Dinner:</b> {', '.join(diet['dinner'])}", normal))
    story.append(Paragraph(f"<b>Healthy Snacks:</b> {', '.join(diet['snacks'])}", normal))
    story.append(Paragraph(f"<b>Water Target:</b> {diet['water_target_l']} L/day", normal))
    story.append(Paragraph(f"<b>Foods to Avoid:</b> {', '.join(diet['foods_to_avoid'])}", normal))

    # Exercise Plan
    story.append(Paragraph("Personalized Exercise Plan", h2))
    ex = plan["exercise"]
    story.append(Paragraph(f"Level: {ex['level']}", normal))
    ex_data = [["Day", "Activity"]] + [[d, a] for d, a in ex["weekly_schedule"].items()]
    story.append(_table(ex_data, [4 * cm, 11 * cm], header=True))

    # Emergency Info
    story.append(Paragraph("Emergency Information", h2))
    story.append(Paragraph(
        "In case of severe symptoms (chest pain, breathing difficulty, fainting, very high/low vitals), "
        "seek immediate medical attention or contact local emergency services.", normal))

    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph(
        "Disclaimer: LifeTwin AI provides general wellness insights based on self-reported data and is not a "
        "medical diagnosis. Always consult a qualified healthcare professional for medical decisions.", small))

    doc.build(story)
    buffer.seek(0)
    return buffer


def _table(data, col_widths, header=False):
    t = Table(data, colWidths=col_widths)
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f6e5b")))
        style.append(("TEXTCOLOR", (0, 0), (-1, 0), colors.white))
        style.append(("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"))
    else:
        style.append(("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f5f3")))
        style.append(("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"))
    t.setStyle(TableStyle(style))
    return t
LIFETWIN_EOF

cat << 'LIFETWIN_EOF' > "lifetwin_ai/requirements.txt"
Flask==3.1.3
Werkzeug==3.1.7
reportlab==4.4.10
LIFETWIN_EOF

cat << 'LIFETWIN_EOF' > "lifetwin_ai/static/css/style.css"
:root {
    --ink: #10241f;
    --paper: #f6f4ee;
    --paper-raised: #ffffff;
    --teal: #0f6e5b;
    --teal-dark: #0a4c3f;
    --teal-light: #e4f0ec;
    --clay: #d97757;
    --amber: #c98a2c;
    --red: #c0392b;
    --line: #dcd6c8;
    --muted: #5a6b64;
    --radius: 14px;
    --shadow: 0 2px 14px rgba(16, 36, 31, 0.06);
}

* { box-sizing: border-box; }

body {
    margin: 0;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--paper);
    color: var(--ink);
    line-height: 1.5;
}

a { color: var(--teal); text-decoration: none; }

h1, h2, h3, h4 {
    font-family: 'Inter', sans-serif;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: var(--teal-dark);
    margin: 0 0 0.4em 0;
}

.container {
    max-width: 1100px;
    margin: 0 auto;
    padding: 32px 24px 64px;
}

/* Navbar */
.navbar {
    background: var(--paper-raised);
    border-bottom: 1px solid var(--line);
    position: sticky;
    top: 0;
    z-index: 50;
}
.navbar-inner {
    max-width: 1100px;
    margin: 0 auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 24px;
}
.brand {
    font-weight: 800;
    font-size: 1.25rem;
    color: var(--teal-dark);
    display: flex;
    align-items: center;
    gap: 6px;
}
.brand-accent { color: var(--clay); }
.nav-links { display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
.nav-links a { color: var(--ink); font-weight: 500; font-size: 0.92rem; }
.nav-links a:hover { color: var(--teal); }
.nav-btn {
    background: var(--teal);
    color: #fff !important;
    padding: 8px 16px;
    border-radius: 999px;
    font-weight: 600 !important;
}
.nav-btn:hover { background: var(--teal-dark); }
.nav-btn-outline {
    border: 1px solid var(--line);
    padding: 7px 14px;
    border-radius: 999px;
}

/* Flash messages */
.flash-wrap { margin-bottom: 20px; }
.flash {
    padding: 12px 16px;
    border-radius: 10px;
    margin-bottom: 8px;
    font-size: 0.92rem;
    font-weight: 500;
    border: 1px solid transparent;
}
.flash-success { background: #e4f5ea; color: #1c6b3d; border-color: #bfe6cd; }
.flash-danger { background: #fbe9e7; color: var(--red); border-color: #f3c9c2; }
.flash-warning { background: #fdf3df; color: #8a6112; border-color: #f2ddab; }

/* Hero (home page) */
.hero {
    display: grid;
    grid-template-columns: 1.1fr 0.9fr;
    gap: 40px;
    align-items: center;
    padding: 40px 0 20px;
}
.hero-eyebrow {
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 0.75rem;
    color: var(--clay);
    font-weight: 700;
    margin-bottom: 10px;
}
.hero h1 { font-size: 2.6rem; line-height: 1.08; }
.hero p.lead { font-size: 1.08rem; color: var(--muted); margin: 16px 0 28px; max-width: 46ch; }
.hero-actions { display: flex; gap: 14px; }
.hero-visual {
    background: linear-gradient(160deg, var(--teal) 0%, var(--teal-dark) 100%);
    border-radius: 24px;
    padding: 32px;
    color: #fff;
    min-height: 320px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    box-shadow: var(--shadow);
}
.twin-ring {
    width: 140px; height: 140px;
    border-radius: 50%;
    border: 6px solid rgba(255,255,255,0.25);
    display: flex; align-items: center; justify-content: center;
    font-size: 2.6rem;
    margin: 0 auto;
    background: rgba(255,255,255,0.08);
}
.hero-stats { display: flex; justify-content: space-between; margin-top: 24px; font-size: 0.85rem; }
.hero-stats div strong { display: block; font-size: 1.4rem; }

.btn {
    display: inline-block;
    padding: 12px 24px;
    border-radius: 999px;
    font-weight: 600;
    cursor: pointer;
    border: none;
    font-size: 0.95rem;
    font-family: inherit;
}
.btn-primary { background: var(--teal); color: #fff; }
.btn-primary:hover { background: var(--teal-dark); }
.btn-secondary { background: transparent; color: var(--teal-dark); border: 1px solid var(--line); }
.btn-secondary:hover { border-color: var(--teal); }
.btn-block { width: 100%; text-align: center; }
.btn-sm { padding: 8px 16px; font-size: 0.85rem; }

/* Feature grid */
.section-title { margin-top: 56px; }
.feature-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 18px;
    margin-top: 20px;
}
.feature-card {
    background: var(--paper-raised);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: 20px;
    box-shadow: var(--shadow);
}
.feature-card .icon { font-size: 1.6rem; margin-bottom: 8px; display: block; }
.feature-card h3 { font-size: 1rem; margin-bottom: 6px; }
.feature-card p { color: var(--muted); font-size: 0.88rem; margin: 0; }

/* Auth forms */
.auth-wrap {
    max-width: 440px;
    margin: 20px auto;
    background: var(--paper-raised);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: 36px;
    box-shadow: var(--shadow);
}
.auth-wrap h2 { text-align: center; }
.auth-sub { text-align: center; color: var(--muted); font-size: 0.9rem; margin-bottom: 24px; }
.auth-switch { text-align: center; margin-top: 16px; font-size: 0.9rem; color: var(--muted); }

/* Forms */
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.form-grid.single { grid-template-columns: 1fr; }
.field { margin-bottom: 16px; display: flex; flex-direction: column; gap: 6px; }
.field label { font-size: 0.85rem; font-weight: 600; color: var(--teal-dark); }
.field .hint { font-size: 0.76rem; color: var(--muted); font-weight: 400; }
input[type=text], input[type=email], input[type=password], input[type=number],
select, textarea {
    padding: 10px 12px;
    border: 1px solid var(--line);
    border-radius: 8px;
    font-size: 0.95rem;
    font-family: inherit;
    background: #fff;
    color: var(--ink);
}
input:focus, select:focus, textarea:focus {
    outline: 2px solid var(--teal);
    outline-offset: 1px;
    border-color: var(--teal);
}
.checkbox-row { display: flex; align-items: center; gap: 8px; font-weight: 500; font-size: 0.9rem; }
.checkbox-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 10px;
    background: var(--teal-light);
    padding: 16px;
    border-radius: 10px;
    margin-bottom: 8px;
}
fieldset { border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px; margin-bottom: 20px; }
legend { font-weight: 700; color: var(--teal-dark); padding: 0 6px; }

/* Card / panel */
.card {
    background: var(--paper-raised);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: 22px;
    box-shadow: var(--shadow);
    margin-bottom: 22px;
}
.card h3 { font-size: 1.05rem; }
.card-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }

.page-header { margin-bottom: 24px; }
.page-header p { color: var(--muted); }

/* Dashboard grid */
.dash-grid {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 22px;
}
@media (max-width: 860px) { .dash-grid { grid-template-columns: 1fr; } .form-grid { grid-template-columns: 1fr; } .hero { grid-template-columns: 1fr; } }

.score-ring-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 14px;
    text-align: center;
}
.score-item { padding: 14px 6px; }
.score-value { font-size: 1.7rem; font-weight: 800; color: var(--teal-dark); }
.score-label { font-size: 0.78rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
.score-bar-track { background: var(--teal-light); border-radius: 999px; height: 8px; margin-top: 8px; overflow: hidden; }
.score-bar-fill { background: var(--teal); height: 100%; border-radius: 999px; }

.overall-score-block {
    display: flex; align-items: center; gap: 20px;
    background: linear-gradient(135deg, var(--teal) 0%, var(--teal-dark) 100%);
    color: #fff;
    border-radius: var(--radius);
    padding: 24px;
    margin-bottom: 20px;
}
.overall-score-num { font-size: 3rem; font-weight: 800; }
.overall-score-block .label { opacity: 0.85; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.06em; }

.alert-box {
    background: #fbe9e7;
    border: 1px solid #f3c9c2;
    color: var(--red);
    padding: 14px 18px;
    border-radius: 10px;
    margin-bottom: 20px;
    font-weight: 600;
}
.alert-box ul { margin: 8px 0 0; padding-left: 20px; font-weight: 400; }

table.data-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
table.data-table th, table.data-table td {
    text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line);
}
table.data-table th { color: var(--muted); font-weight: 600; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; }

.badge { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 700; }
.badge-low { background: #e4f5ea; color: #1c6b3d; }
.badge-medium { background: #fdf3df; color: #8a6112; }
.badge-high { background: #fbe9e7; color: var(--red); }

.disease-bar-row { margin-bottom: 14px; }
.disease-bar-row .top { display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 4px; }
.disease-track { background: var(--teal-light); border-radius: 999px; height: 10px; position: relative; overflow: hidden; }
.disease-fill-current { background: var(--teal); height: 100%; position: absolute; left: 0; top: 0; border-radius: 999px; }
.disease-fill-future { background: var(--clay); height: 4px; position: absolute; left: 0; bottom: -1px; opacity: 0.7; }
.disease-reasons { font-size: 0.78rem; color: var(--muted); margin-top: 4px; }

.plan-columns { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 18px; }
.plan-col h4 { font-size: 0.95rem; margin-bottom: 8px; }
.plan-col ul { margin: 0; padding-left: 18px; font-size: 0.88rem; color: var(--ink); }
.week-table { width: 100%; font-size: 0.85rem; border-collapse: collapse; }
.week-table td { padding: 6px 8px; border-bottom: 1px dashed var(--line); }
.week-table td:first-child { font-weight: 700; color: var(--teal-dark); width: 60px; }

/* Coach chat */
.chat-window {
    background: var(--paper-raised);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    height: 480px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}
.chat-messages { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; }
.msg { max-width: 78%; padding: 10px 14px; border-radius: 14px; font-size: 0.92rem; line-height: 1.45; }
.msg-user { align-self: flex-end; background: var(--teal); color: #fff; border-bottom-right-radius: 4px; }
.msg-ai { align-self: flex-start; background: var(--teal-light); color: var(--ink); border-bottom-left-radius: 4px; }
.chat-input-row { display: flex; border-top: 1px solid var(--line); padding: 12px; gap: 10px; }
.chat-input-row input { flex: 1; }
.suggested-qs { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.chip {
    background: var(--teal-light); color: var(--teal-dark); border: none;
    padding: 8px 14px; border-radius: 999px; font-size: 0.82rem; cursor: pointer; font-weight: 600;
}
.chip:hover { background: var(--teal); color: #fff; }

/* Footer */
.site-footer {
    text-align: center;
    padding: 30px 20px 40px;
    color: var(--muted);
    font-size: 0.85rem;
    border-top: 1px solid var(--line);
    margin-top: 40px;
}
.site-footer .disclaimer { font-size: 0.75rem; margin-top: 6px; opacity: 0.8; }

.empty-state { text-align: center; padding: 30px; color: var(--muted); }
.empty-state a { font-weight: 700; }

.symptom-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px;
}
.symptom-chip {
    display: flex; align-items: center; gap: 8px;
    background: var(--teal-light); border-radius: 10px; padding: 10px 12px; font-size: 0.9rem; font-weight: 500;
}
LIFETWIN_EOF

cat << 'LIFETWIN_EOF' > "lifetwin_ai/templates/base.html"
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{% block title %}LifeTwin AI{% endblock %}</title>
<link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
</head>
<body>
<header class="navbar">
    <div class="navbar-inner">
        <a href="{{ url_for('home') }}" class="brand">
            <span class="brand-icon">🫀</span> LifeTwin <span class="brand-accent">AI</span>
        </a>
        <nav class="nav-links">
            {% if session.user_id %}
                <a href="{{ url_for('dashboard') }}">Dashboard</a>
                <a href="{{ url_for('profile') }}">Profile</a>
                <a href="{{ url_for('data_entry') }}">Vitals</a>
                <a href="{{ url_for('lab_reports') }}">Lab Reports</a>
                <a href="{{ url_for('symptoms') }}">Symptoms</a>
                <a href="{{ url_for('coach') }}">AI Coach</a>
                <a href="{{ url_for('logout') }}" class="nav-btn-outline">Logout</a>
            {% else %}
                <a href="{{ url_for('login') }}">Login</a>
                <a href="{{ url_for('register') }}" class="nav-btn">Get Started</a>
            {% endif %}
        </nav>
    </div>
</header>

<main class="container">
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            <div class="flash-wrap">
            {% for category, message in messages %}
                <div class="flash flash-{{ category }}">{{ message }}</div>
            {% endfor %}
            </div>
        {% endif %}
    {% endwith %}

    {% block content %}{% endblock %}
</main>

<footer class="site-footer">
    <p>LifeTwin AI — Building a Digital Health Twin that predicts future health risks before they become diseases.</p>
    <p class="disclaimer">Disclaimer: LifeTwin AI provides general wellness insights based on self-reported data and is not a substitute for professional medical advice.</p>
</footer>

{% block scripts %}{% endblock %}
</body>
</html>
LIFETWIN_EOF

cat << 'LIFETWIN_EOF' > "lifetwin_ai/templates/coach.html"
{% extends "base.html" %}
{% block title %}AI Health Coach — LifeTwin AI{% endblock %}
{% block content %}
<div class="page-header">
    <h1>Your AI Health Coach</h1>
    <p>Ask questions about your health data, and get answers grounded in your own profile.</p>
</div>

<div class="chat-window">
    <div class="chat-messages" id="chatMessages">
        <div class="msg msg-ai">Hi! I'm your AI Health Coach. Ask me about your blood pressure, cholesterol, diet, exercise, sleep, or disease risk — I'll answer using your own health data.</div>
    </div>
    <div class="chat-input-row">
        <input type="text" id="chatInput" placeholder="Ask a question about your health...">
        <button class="btn btn-primary" id="sendBtn">Send</button>
    </div>
</div>

<div class="suggested-qs">
    <button class="chip" data-q="Why is my blood pressure high?">Why is my blood pressure high?</button>
    <button class="chip" data-q="What should I eat today?">What should I eat today?</button>
    <button class="chip" data-q="How can I reduce my cholesterol?">How can I reduce my cholesterol?</button>
    <button class="chip" data-q="Why is my health score decreasing?">Why is my health score decreasing?</button>
    <button class="chip" data-q="What exercises are best for me?">What exercises are best for me?</button>
    <button class="chip" data-q="What is my diabetes risk?">What is my diabetes risk?</button>
</div>
{% endblock %}

{% block scripts %}
<script>
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');

function addMessage(text, who) {
    const div = document.createElement('div');
    div.className = 'msg ' + (who === 'user' ? 'msg-user' : 'msg-ai');
    div.textContent = text;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function sendQuestion(question) {
    if (!question.trim()) return;
    addMessage(question, 'user');
    chatInput.value = '';
    const thinking = document.createElement('div');
    thinking.className = 'msg msg-ai';
    thinking.textContent = 'Thinking...';
    chatMessages.appendChild(thinking);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const res = await fetch('{{ url_for("api_coach") }}', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });
        const data = await res.json();
        thinking.textContent = data.answer;
    } catch (e) {
        thinking.textContent = "Sorry, something went wrong. Please try again.";
    }
}

sendBtn.addEventListener('click', () => sendQuestion(chatInput.value));
chatInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') sendQuestion(chatInput.value); });
document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => sendQuestion(chip.dataset.q));
});
</script>
{% endblock %}
LIFETWIN_EOF

cat << 'LIFETWIN_EOF' > "lifetwin_ai/templates/dashboard.html"
{% extends "base.html" %}
{% block title %}Dashboard — LifeTwin AI{% endblock %}
{% block content %}

<div class="page-header">
    <h1>Hello, {{ user.full_name.split(' ')[0] }} 👋</h1>
    <p>Here's the current state of your Digital Health Twin.</p>
</div>

{% if alerts %}
<div class="alert-box">
    🚨 Emergency Health Alert — please seek medical attention
    <ul>
        {% for a in alerts %}<li>{{ a }}</li>{% endfor %}
    </ul>
</div>
{% endif %}

<div class="overall-score-block">
    <div class="score-ring" style="font-size:0.9rem;">
        <div class="label">Overall Health Score</div>
        <div class="overall-score-num">{{ scores.overall }}<span style="font-size:1.2rem;">/100</span></div>
        <div>BMI: {{ scores.bmi or '—' }} ({{ scores.bmi_category }})</div>
    </div>
    <div style="flex:1;">
        <a href="{{ url_for('download_report') }}" class="btn" style="background:#fff;color:var(--teal-dark);">⬇ Download PDF Health Report</a>
    </div>
</div>

<div class="card">
    <h3>Health Scores</h3>
    <div class="score-ring-grid">
        {% for label, key in [('Physical','physical'),('Nutrition','nutrition'),('Sleep','sleep'),('Hydration','hydration'),('Mental','mental')] %}
        <div class="score-item">
            <div class="score-value">{{ scores[key] }}</div>
            <div class="score-label">{{ label }}</div>
            <div class="score-bar-track"><div class="score-bar-fill" style="width:{{ scores[key] }}%;"></div></div>
        </div>
        {% endfor %}
    </div>
</div>

<div class="dash-grid">
    <div>
        <div class="card">
            <h3>Future Disease Risk Prediction</h3>
            {% for disease, v in disease_risks.items() %}
            <div class="disease-bar-row">
                <div class="top">
                    <span><strong>{{ disease }}</strong></span>
                    <span>{{ v.current_risk }}% now → {{ v.future_risk }}% in 5 yrs</span>
                </div>
                <div class="disease-track">
                    <div class="disease-fill-current" style="width:{{ v.current_risk }}%;"></div>
                    <div class="disease-fill-future" style="width:{{ v.future_risk }}%;"></div>
                </div>
                <div class="disease-reasons">{{ v.reasons | join(', ') }}</div>
            </div>
            {% endfor %}
        </div>

        <div class="card">
            <h3>Symptom Analysis</h3>
            {% if symptom_results %}
                {% for s in symptom_results %}
                <div style="margin-bottom:14px; padding-bottom:12px; border-bottom:1px solid var(--line);">
                    <div class="card-row" style="margin-bottom:4px;">
                        <strong>{{ s.symptom }}</strong>
                        <span class="badge badge-{{ s.risk_level|lower }}">{{ s.risk_level }} Risk</span>
                    </div>
                    <div style="font-size:0.88rem; color:var(--muted);">Possible: {{ s.possible_conditions | join(', ') }}</div>
                    <div style="font-size:0.88rem; margin-top:4px;">{{ s.advice }}</div>
                </div>
                {% endfor %}
            {% else %}
                <div class="empty-state">No current symptoms logged. <a href="{{ url_for('symptoms') }}">Log symptoms →</a></div>
            {% endif %}
        </div>

        <div class="card">
            <h3>Personalized Prevention Plan</h3>
            <div class="plan-columns">
                <div class="plan-col">
                    <h4>🥗 Diet Plan</h4>
                    <p><strong>Breakfast:</strong></p>
                    <ul>{% for item in plan.diet.breakfast %}<li>{{ item }}</li>{% endfor %}</ul>
                    <p><strong>Lunch:</strong></p>
                    <ul>{% for item in plan.diet.lunch %}<li>{{ item }}</li>{% endfor %}</ul>
                    <p><strong>Dinner:</strong></p>
                    <ul>{% for item in plan.diet.dinner %}<li>{{ item }}</li>{% endfor %}</ul>
                    <p><strong>Water Target:</strong> {{ plan.diet.water_target_l }} L/day</p>
                    <p><strong>Avoid:</strong> {{ plan.diet.foods_to_avoid | join(', ') }}</p>
                </div>
                <div class="plan-col">
                    <h4>🏃 Exercise Plan ({{ plan.exercise.level }})</h4>
                    <table class="week-table">
                        {% for day, activity in plan.exercise.weekly_schedule.items() %}
                        <tr><td>{{ day }}</td><td>{{ activity }}</td></tr>
                        {% endfor %}
                    </table>
                </div>
                <div class="plan-col">
                    <h4>🧘 Lifestyle Plan</h4>
                    <p>{{ plan.lifestyle.sleep_schedule }}</p>
                    <p>{{ plan.lifestyle.stress_management }}</p>
                    <p>{{ plan.lifestyle.weight_management }}</p>
                    <ul>{% for g in plan.lifestyle.daily_goals %}<li>{{ g }}</li>{% endfor %}</ul>
                </div>
                <div class="plan-col">
                    <h4>🛡 Preventive Care</h4>
                    <ul>
                        <li>{{ plan.preventive_care.checkup_reminder }}</li>
                        <li>{{ plan.preventive_care.medication_reminder }}</li>
                        <li>{{ plan.preventive_care.vaccination_reminder }}</li>
                        {% if plan.preventive_care.priority_screenings %}
                            {% for s in plan.preventive_care.priority_screenings %}<li>{{ s }}</li>{% endfor %}
                        {% endif %}
                    </ul>
                </div>
            </div>
        </div>
    </div>

    <div>
        <div class="card">
            <h3>Monthly Progress</h3>
            <canvas id="scoreChart" height="200"></canvas>
        </div>
        <div class="card">
            <h3>Vitals Trend</h3>
            <canvas id="vitalsChart" height="200"></canvas>
        </div>
        <div class="card">
            <h3>Quick Actions</h3>
            <p><a href="{{ url_for('data_entry') }}" class="btn btn-secondary btn-block" style="margin-bottom:8px;">➕ Log Vitals</a></p>
            <p><a href="{{ url_for('symptoms') }}" class="btn btn-secondary btn-block" style="margin-bottom:8px;">🩺 Update Symptoms</a></p>
            <p><a href="{{ url_for('lab_reports') }}" class="btn btn-secondary btn-block" style="margin-bottom:8px;">🧪 Add Lab Report</a></p>
            <p><a href="{{ url_for('coach') }}" class="btn btn-secondary btn-block">💬 Ask AI Health Coach</a></p>
        </div>
    </div>
</div>

{% endblock %}

{% block scripts %}
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<script>
const scoreHistory = {{ score_history | tojson }};
const vitalsHistory = {{ vitals_history | tojson }};

const scoreLabels = scoreHistory.map(r => r.computed_at.slice(5, 16));
new Chart(document.getElementById('scoreChart'), {
    type: 'line',
    data: {
        labels: scoreLabels,
        datasets: [{
            label: 'Overall Health Score',
            data: scoreHistory.map(r => r.overall),
            borderColor: '#0f6e5b',
            backgroundColor: 'rgba(15,110,91,0.12)',
            tension: 0.3,
            fill: true,
        }]
    },
    options: { plugins: { legend: { display: false } }, scales: { y: { min: 0, max: 100 } } }
});

const vitalsLabels = vitalsHistory.map(r => r.recorded_at.slice(5, 16));
new Chart(document.getElementById('vitalsChart'), {
    type: 'line',
    data: {
        labels: vitalsLabels,
        datasets: [
            { label: 'Systolic BP', data: vitalsHistory.map(r => r.systolic), borderColor: '#d97757', tension: 0.3 },
            { label: 'Blood Sugar', data: vitalsHistory.map(r => r.blood_sugar), borderColor: '#c98a2c', tension: 0.3 },
            { label: 'Heart Rate', data: vitalsHistory.map(r => r.heart_rate), borderColor: '#0f6e5b', tension: 0.3 },
        ]
    },
    options: { plugins: { legend: { position: 'bottom' } } }
});
</script>
{% endblock %}
LIFETWIN_EOF

cat << 'LIFETWIN_EOF' > "lifetwin_ai/templates/data_entry.html"
{% extends "base.html" %}
{% block title %}Health Data Entry — LifeTwin AI{% endblock %}
{% block content %}
<div class="page-header">
    <h1>Log Your Vital Signs</h1>
    <p>Don't have a value handy? Leave it blank and add it later — every field is optional.</p>
</div>

<div class="card">
    <form method="POST">
        <div class="form-grid">
            <div class="field">
                <label for="systolic">Blood Pressure — Systolic (mmHg)</label>
                <input type="number" step="0.1" id="systolic" name="systolic" placeholder="e.g. 120">
            </div>
            <div class="field">
                <label for="diastolic">Blood Pressure — Diastolic (mmHg)</label>
                <input type="number" step="0.1" id="diastolic" name="diastolic" placeholder="e.g. 80">
            </div>
            <div class="field">
                <label for="blood_sugar">Blood Sugar — Fasting (mg/dL)</label>
                <input type="number" step="0.1" id="blood_sugar" name="blood_sugar" placeholder="e.g. 95">
            </div>
            <div class="field">
                <label for="heart_rate">Heart Rate (bpm)</label>
                <input type="number" step="0.1" id="heart_rate" name="heart_rate" placeholder="e.g. 72">
            </div>
            <div class="field">
                <label for="spo2">Oxygen Saturation — SpO2 (%)</label>
                <input type="number" step="0.1" id="spo2" name="spo2" placeholder="e.g. 98">
            </div>
            <div class="field">
                <label for="temperature">Body Temperature (°F)</label>
                <input type="number" step="0.1" id="temperature" name="temperature" placeholder="e.g. 98.6">
            </div>
            <div class="field">
                <label for="cholesterol">Total Cholesterol (mg/dL) <span class="hint">Optional</span></label>
                <input type="number" step="0.1" id="cholesterol" name="cholesterol" placeholder="e.g. 180">
            </div>
        </div>
        <button type="submit" class="btn btn-primary">Save Health Data</button>
    </form>
</div>

{% if latest %}
<div class="card">
    <h3>Last Recorded ({{ latest.recorded_at }})</h3>
    <table class="data-table">
        <tr><th>BP</th><td>{{ latest.systolic or '-' }}/{{ latest.diastolic or '-' }} mmHg</td></tr>
        <tr><th>Blood Sugar</th><td>{{ latest.blood_sugar or '-' }} mg/dL</td></tr>
        <tr><th>Heart Rate</th><td>{{ latest.heart_rate or '-' }} bpm</td></tr>
        <tr><th>SpO2</th><td>{{ latest.spo2 or '-' }} %</td></tr>
        <tr><th>Temperature</th><td>{{ latest.temperature or '-' }} °F</td></tr>
        <tr><th>Cholesterol</th><td>{{ latest.cholesterol or '-' }} mg/dL</td></tr>
    </table>
</div>
{% endif %}
{% endblock %}
LIFETWIN_EOF

cat << 'LIFETWIN_EOF' > "lifetwin_ai/templates/index.html"
{% extends "base.html" %}
{% block title %}LifeTwin AI — Your Digital Health Twin{% endblock %}
{% block content %}

<section class="hero">
    <div>
        <div class="hero-eyebrow">Preventive Healthcare, Powered by AI</div>
        <h1>Meet the digital twin of your health — before disease does.</h1>
        <p class="lead">LifeTwin AI builds a living profile of your body from what you already know: your vitals, habits, and history. No wearables required. Just answers about what's coming, and what to do about it.</p>
        <div class="hero-actions">
            <a href="{{ url_for('register') }}" class="btn btn-primary">Create your Health Twin</a>
            <a href="{{ url_for('login') }}" class="btn btn-secondary">I already have an account</a>
        </div>
    </div>
    <div class="hero-visual">
        <div class="twin-ring">🫀</div>
        <div class="hero-stats">
            <div><strong>13</strong>Health Modules</div>
            <div><strong>0</strong>Wearables Needed</div>
            <div><strong>10+</strong>Diseases Tracked</div>
        </div>
    </div>
</section>

<h2 class="section-title">What your Health Twin does</h2>
<div class="feature-grid">
    <div class="feature-card">
        <span class="icon">📋</span>
        <h3>Manual Health Profile</h3>
        <p>Enter your vitals, lifestyle, and medical history yourself — built for places where smartwatches aren't the norm.</p>
    </div>
    <div class="feature-card">
        <span class="icon">🧠</span>
        <h3>Explainable AI Scoring</h3>
        <p>Get a Physical, Nutrition, Sleep, Hydration, and Mental Wellness score — each one with the reasons behind it.</p>
    </div>
    <div class="feature-card">
        <span class="icon">🩺</span>
        <h3>Symptom Analysis</h3>
        <p>Log symptoms and get possible conditions, a risk level, and clear next steps — not a diagnosis, a direction.</p>
    </div>
    <div class="feature-card">
        <span class="icon">📈</span>
        <h3>Future Disease Risk</h3>
        <p>See your current and 5-year risk for conditions like diabetes, hypertension, and heart disease — with reasons why.</p>
    </div>
    <div class="feature-card">
        <span class="icon">🥗</span>
        <h3>Personalized Prevention Plan</h3>
        <p>A diet, exercise, and lifestyle plan generated around your real numbers — not generic advice.</p>
    </div>
    <div class="feature-card">
        <span class="icon">🚨</span>
        <h3>Emergency Detection</h3>
        <p>Dangerous vitals trigger an immediate alert, so nothing critical slips through unnoticed.</p>
    </div>
    <div class="feature-card">
        <span class="icon">💬</span>
        <h3>AI Health Coach</h3>
        <p>Ask "Why is my blood pressure high?" and get an answer grounded in your own health data.</p>
    </div>
    <div class="feature-card">
        <span class="icon">📄</span>
        <h3>Downloadable Reports</h3>
        <p>Export a complete PDF health report to share with your doctor or keep for your records.</p>
    </div>
</div>

{% endblock %}
LIFETWIN_EOF

cat << 'LIFETWIN_EOF' > "lifetwin_ai/templates/lab_reports.html"
{% extends "base.html" %}
{% block title %}Lab Reports — LifeTwin AI{% endblock %}
{% block content %}
<div class="page-header">
    <h1>Laboratory Reports <span class="hint">(Optional)</span></h1>
    <p>Add values from your most recent lab report to sharpen your disease risk predictions. Skip anything you don't have.</p>
</div>

<div class="card">
    <form method="POST">
        <div class="form-grid">
            <div class="field">
                <label for="hba1c">HbA1c (%)</label>
                <input type="number" step="0.01" id="hba1c" name="hba1c" placeholder="e.g. 5.4">
            </div>
            <div class="field">
                <label for="lab_cholesterol">Cholesterol — Lab (mg/dL)</label>
                <input type="number" step="0.1" id="lab_cholesterol" name="lab_cholesterol" placeholder="e.g. 190">
            </div>
            <div class="field">
                <label for="hemoglobin">Hemoglobin (g/dL)</label>
                <input type="number" step="0.1" id="hemoglobin" name="hemoglobin" placeholder="e.g. 13.5">
            </div>
            <div class="field">
                <label for="creatinine">Creatinine (mg/dL)</label>
                <input type="number" step="0.01" id="creatinine" name="creatinine" placeholder="e.g. 0.9">
            </div>
            <div class="field">
                <label for="liver_alt">Liver Function — ALT (U/L)</label>
                <input type="number" step="0.1" id="liver_alt" name="liver_alt" placeholder="e.g. 28">
            </div>
            <div class="field">
                <label for="liver_ast">Liver Function — AST (U/L)</label>
                <input type="number" step="0.1" id="liver_ast" name="liver_ast" placeholder="e.g. 25">
            </div>
            <div class="field">
                <label for="kidney_egfr">Kidney Function — eGFR</label>
                <input type="number" step="0.1" id="kidney_egfr" name="kidney_egfr" placeholder="e.g. 95">
            </div>
        </div>
        <button type="submit" class="btn btn-primary">Save Lab Report</button>
    </form>
</div>

{% if latest %}
<div class="card">
    <h3>Last Recorded ({{ latest.recorded_at }})</h3>
    <table class="data-table">
        <tr><th>HbA1c</th><td>{{ latest.hba1c or '-' }} %</td></tr>
        <tr><th>Cholesterol</th><td>{{ latest.lab_cholesterol or '-' }} mg/dL</td></tr>
        <tr><th>Hemoglobin</th><td>{{ latest.hemoglobin or '-' }} g/dL</td></tr>
        <tr><th>Creatinine</th><td>{{ latest.creatinine or '-' }} mg/dL</td></tr>
        <tr><th>Liver ALT / AST</th><td>{{ latest.liver_alt or '-' }} / {{ latest.liver_ast or '-' }} U/L</td></tr>
        <tr><th>Kidney eGFR</th><td>{{ latest.kidney_egfr or '-' }}</td></tr>
    </table>
</div>
{% endif %}
{% endblock %}
LIFETWIN_EOF

cat << 'LIFETWIN_EOF' > "lifetwin_ai/templates/login.html"
{% extends "base.html" %}
{% block title %}Log in — LifeTwin AI{% endblock %}
{% block content %}
<div class="auth-wrap">
    <h2>Welcome back</h2>
    <p class="auth-sub">Log in to see your latest health insights.</p>
    <form method="POST">
        <div class="field">
            <label for="email">Email</label>
            <input type="email" id="email" name="email" required autofocus>
        </div>
        <div class="field">
            <label for="password">Password</label>
            <input type="password" id="password" name="password" required>
        </div>
        <button type="submit" class="btn btn-primary btn-block">Log In</button>
    </form>
    <p class="auth-switch">New to LifeTwin AI? <a href="{{ url_for('register') }}">Create an account</a></p>
</div>
{% endblock %}
LIFETWIN_EOF

cat << 'LIFETWIN_EOF' > "lifetwin_ai/templates/profile.html"
{% extends "base.html" %}
{% block title %}Health Profile — LifeTwin AI{% endblock %}
{% block content %}
<div class="page-header">
    <h1>Your Health Profile</h1>
    <p>This information powers every prediction your Health Twin makes. The more complete it is, the more accurate your insights will be.</p>
</div>

<form method="POST">
    <fieldset>
        <legend>Personal Information</legend>
        <div class="form-grid">
            <div class="field">
                <label for="height_cm">Height (cm)</label>
                <input type="number" step="0.1" id="height_cm" name="height_cm" value="{{ profile.height_cm or '' }}">
            </div>
            <div class="field">
                <label for="weight_kg">Weight (kg)</label>
                <input type="number" step="0.1" id="weight_kg" name="weight_kg" value="{{ profile.weight_kg or '' }}">
            </div>
        </div>
    </fieldset>

    <fieldset>
        <legend>Lifestyle Information</legend>
        <div class="form-grid">
            <div class="field">
                <label for="smoking">Smoking</label>
                <select id="smoking" name="smoking">
                    {% for v in ['never','former','occasional','regular'] %}
                    <option value="{{ v }}" {% if profile.smoking==v %}selected{% endif %}>{{ v|capitalize }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="field">
                <label for="alcohol">Alcohol Consumption</label>
                <select id="alcohol" name="alcohol">
                    {% for v in ['never','occasional','moderate','heavy'] %}
                    <option value="{{ v }}" {% if profile.alcohol==v %}selected{% endif %}>{{ v|capitalize }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="field">
                <label for="exercise_freq">Exercise Frequency</label>
                <select id="exercise_freq" name="exercise_freq">
                    {% for v in ['none','rarely','1-2 times/week','3-4 times/week','daily'] %}
                    <option value="{{ v }}" {% if profile.exercise_freq==v %}selected{% endif %}>{{ v }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="field">
                <label for="sleep_hours">Sleep Hours (avg/night)</label>
                <input type="number" step="0.5" id="sleep_hours" name="sleep_hours" value="{{ profile.sleep_hours or '' }}">
            </div>
            <div class="field">
                <label for="water_intake_l">Water Intake (L/day)</label>
                <input type="number" step="0.1" id="water_intake_l" name="water_intake_l" value="{{ profile.water_intake_l or '' }}">
            </div>
            <div class="field">
                <label for="stress_level">Stress Level</label>
                <select id="stress_level" name="stress_level">
                    {% for v in ['low','moderate','high','severe'] %}
                    <option value="{{ v }}" {% if profile.stress_level==v %}selected{% endif %}>{{ v|capitalize }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="field">
                <label for="occupation">Occupation</label>
                <input type="text" id="occupation" name="occupation" value="{{ profile.occupation or '' }}">
            </div>
        </div>
    </fieldset>

    <fieldset>
        <legend>Medical History</legend>
        <div class="checkbox-grid">
            {% set conditions = [('diabetes','Diabetes'),('hypertension','High Blood Pressure'),('heart_disease','Heart Disease'),('kidney_disease','Kidney Disease'),('asthma','Asthma'),('thyroid_disease','Thyroid Disease')] %}
            {% for key, label in conditions %}
            <label class="checkbox-row">
                <input type="checkbox" name="{{ key }}" {% if profile.get(key) %}checked{% endif %}> {{ label }}
            </label>
            {% endfor %}
        </div>
        <div class="form-grid" style="margin-top: 12px;">
            <div class="field">
                <label for="allergies">Allergies</label>
                <input type="text" id="allergies" name="allergies" value="{{ profile.allergies or '' }}" placeholder="e.g. Peanuts, Dust">
            </div>
            <div class="field">
                <label for="current_medications">Current Medications</label>
                <input type="text" id="current_medications" name="current_medications" value="{{ profile.current_medications or '' }}" placeholder="e.g. Metformin 500mg">
            </div>
        </div>
    </fieldset>

    <fieldset>
        <legend>Family Medical History</legend>
        <div class="checkbox-grid">
            {% set fam = [('family_diabetes','Diabetes'),('family_heart_disease','Heart Disease'),('family_stroke','Stroke'),('family_cancer','Cancer'),('family_kidney_disease','Kidney Disease')] %}
            {% for key, label in fam %}
            <label class="checkbox-row">
                <input type="checkbox" name="{{ key }}" {% if profile.get(key) %}checked{% endif %}> {{ label }}
            </label>
            {% endfor %}
        </div>
    </fieldset>

    <button type="submit" class="btn btn-primary">Save Health Profile</button>
</form>
{% endblock %}
LIFETWIN_EOF

cat << 'LIFETWIN_EOF' > "lifetwin_ai/templates/register.html"
{% extends "base.html" %}
{% block title %}Create your account — LifeTwin AI{% endblock %}
{% block content %}
<div class="auth-wrap">
    <h2>Create your Health Twin</h2>
    <p class="auth-sub">Takes less than a minute to get started.</p>
    <form method="POST">
        <div class="field">
            <label for="full_name">Full Name</label>
            <input type="text" id="full_name" name="full_name" required>
        </div>
        <div class="field">
            <label for="email">Email</label>
            <input type="email" id="email" name="email" required>
        </div>
        <div class="field">
            <label for="password">Password</label>
            <input type="password" id="password" name="password" required minlength="6">
        </div>
        <div class="form-grid">
            <div class="field">
                <label for="age">Age</label>
                <input type="number" id="age" name="age" min="1" max="120">
            </div>
            <div class="field">
                <label for="gender">Gender</label>
                <select id="gender" name="gender">
                    <option value="">Select</option>
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                </select>
            </div>
        </div>
        <button type="submit" class="btn btn-primary btn-block">Create Account</button>
    </form>
    <p class="auth-switch">Already have an account? <a href="{{ url_for('login') }}">Log in</a></p>
</div>
{% endblock %}
LIFETWIN_EOF

cat << 'LIFETWIN_EOF' > "lifetwin_ai/templates/symptoms.html"
{% extends "base.html" %}
{% block title %}Current Symptoms — LifeTwin AI{% endblock %}
{% block content %}
<div class="page-header">
    <h1>How are you feeling today?</h1>
    <p>Select any symptoms you're currently experiencing. Your AI Health Twin will analyze them alongside your health profile.</p>
</div>

<div class="card">
    <form method="POST">
        <div class="symptom-grid">
            {% for option in options %}
            <label class="symptom-chip">
                <input type="checkbox" name="symptoms" value="{{ option }}" {% if option in current %}checked{% endif %}>
                {{ option }}
            </label>
            {% endfor %}
        </div>
        <div style="margin-top: 18px;">
            <button type="submit" class="btn btn-primary">Analyze My Symptoms</button>
        </div>
    </form>
</div>
{% endblock %}
LIFETWIN_EOF

touch "lifetwin_ai/instance/.gitkeep"

echo "Project created in ./lifetwin_ai"
echo ""
echo "Next steps:"
echo "  cd lifetwin_ai"
echo "  python3 -m venv venv && source venv/bin/activate"
echo "  pip install -r requirements.txt"
echo "  python app.py"
echo ""
echo "Then open http://127.0.0.1:5000"
