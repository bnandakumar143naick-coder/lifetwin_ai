"""
LifeTwin AI - Personalized Prevention Plan Generator
--------------------------------------------------------
Builds a diet, exercise, and lifestyle plan based on the profile, scores,
and disease risks. Rule-based and explainable.
"""


def generate_diet_plan(profile, risks):
    bmi = profile.bmi
    high_diabetes = risks.get("Diabetes", {}).get("current", 0) >= 40
    high_bp = risks.get("Hypertension", {}).get("current", 0) >= 40
    high_chol = risks.get("High Cholesterol", {}).get("current", 0) >= 40

    breakfast = ["Oats/whole-grain porridge", "1 boiled egg or lentils", "A portion of seasonal fruit"]
    lunch = ["Brown rice or 2 whole-wheat rotis", "Dal/legumes + a green vegetable", "Salad + curd"]
    dinner = ["Light khichdi or grilled vegetables + rotis", "Soup or steamed vegetables"]
    snacks = ["Roasted chana/nuts (unsalted)", "Buttermilk or green tea", "A fruit"]
    avoid = ["Sugary drinks and sweets", "Deep-fried foods", "Excess salt/packaged snacks"]

    if high_diabetes:
        avoid.append("White rice / refined flour in large portions — prefer whole grains")
        breakfast.append("Avoid sugary tea/coffee — prefer unsweetened")
    if high_bp:
        avoid.append("Pickles, papad, and high-sodium processed food")
    if high_chol:
        avoid.append("Red meat, full-fat dairy, and fried snacks")
        dinner.append("Include more fiber-rich vegetables")
    if bmi and bmi >= 25:
        snacks = ["Cucumber/carrot sticks", "Buttermilk", "Handful of nuts (unsalted)"]

    return {
        "breakfast": breakfast,
        "lunch": lunch,
        "dinner": dinner,
        "snacks": snacks,
        "water_target_l": 2.5 if not profile.water_intake_l or profile.water_intake_l < 2.5 else profile.water_intake_l,
        "avoid": avoid,
    }


def generate_exercise_plan(profile, risks):
    bmi = profile.bmi
    heart_risk = risks.get("Heart Disease", {}).get("current", 0) >= 40
    arthritis_risk = risks.get("Arthritis", {}).get("current", 0) >= 40

    if heart_risk or (bmi and bmi >= 32):
        intensity_note = "Start with low-impact activity and consult a doctor before intense exercise"
        weekly = {
            "Mon": "20-min brisk walk",
            "Tue": "Gentle yoga / stretching",
            "Wed": "Rest or light walk",
            "Thu": "20-min brisk walk",
            "Fri": "Gentle yoga / stretching",
            "Sat": "30-min walk",
            "Sun": "Rest",
        }
    elif arthritis_risk:
        intensity_note = "Focus on low-impact, joint-friendly movement"
        weekly = {
            "Mon": "Swimming or cycling (20 min)",
            "Tue": "Stretching / mobility exercises",
            "Wed": "Walking (25 min)",
            "Thu": "Rest",
            "Fri": "Swimming or cycling (20 min)",
            "Sat": "Yoga",
            "Sun": "Rest",
        }
    else:
        intensity_note = "Maintain a balanced mix of cardio and strength training"
        weekly = {
            "Mon": "30-min brisk walk / jog",
            "Tue": "Strength training (bodyweight/gym)",
            "Wed": "Yoga / stretching",
            "Thu": "30-min brisk walk / jog",
            "Fri": "Strength training (bodyweight/gym)",
            "Sat": "Sport / recreational activity (45 min)",
            "Sun": "Rest / light stretching",
        }

    return {"note": intensity_note, "weekly_schedule": weekly}


def generate_lifestyle_plan(profile, scores):
    goals = []
    if scores["sleep"]["score"] < 70:
        goals.append("Aim for 7-9 hours of sleep with a consistent sleep/wake time")
    if scores["hydration"]["score"] < 70:
        goals.append("Increase water intake to at least 2.5 L/day")
    if scores["mental"]["score"] < 70:
        goals.append("Practice 10 minutes of daily relaxation/breathing exercises to manage stress")
    if profile.smoking and profile.smoking != "Never":
        goals.append("Work toward reducing/quitting smoking — consider a cessation program")
    if profile.alcohol == "Regular":
        goals.append("Reduce alcohol consumption to occasional/moderate levels")
    if not goals:
        goals.append("Keep up the good habits — maintain your current routine")

    return {
        "sleep_schedule": "Consistent 7-9 hours, same bedtime/wake time daily",
        "stress_management": "Meditation, deep breathing, or a relaxing hobby for 10-15 min/day",
        "daily_goals": goals,
    }


def generate_preventive_care(risks, age):
    reminders = ["Annual full-body health check-up"]
    if age >= 40:
        reminders.append("Blood pressure and blood sugar screening every 6 months")
        reminders.append("Cholesterol (lipid profile) test annually")
    if risks.get("Diabetes", {}).get("current", 0) >= 30:
        reminders.append("HbA1c test every 3-6 months")
    if risks.get("Kidney Disease", {}).get("current", 0) >= 30:
        reminders.append("Kidney function test (creatinine/eGFR) annually")
    if risks.get("Heart Disease", {}).get("current", 0) >= 40:
        reminders.append("ECG / cardiac screening consultation")
    reminders.append("Keep vaccinations (flu, tetanus, etc.) up to date")
    return reminders
