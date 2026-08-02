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
