"""
LifeTwin AI - AI Health Coach
---------------------------------
Keyword/intent-based coach that answers using the user's own profile,
vitals, scores and risk predictions - fully explainable, no external calls
needed (works offline, good for rural/low-connectivity use).
"""

import re


def answer_question(question, profile, vitals, scores, risks, diet_plan, exercise_plan):
    q = question.lower()

    def has(*words):
        return any(w in q for w in words)

    # Blood pressure
    if has("blood pressure", "bp") and has("why", "high", "reason"):
        if vitals and vitals.systolic_bp:
            reasons = risks.get("Hypertension", {}).get("reasons", [])
            if vitals.systolic_bp >= 130:
                base = f"Your latest reading was {vitals.systolic_bp}/{vitals.diastolic_bp} mmHg, which is elevated."
                if reasons:
                    base += " Contributing factors: " + "; ".join(reasons) + "."
                base += " Reduce salt intake, manage stress, and stay active. Consult a doctor if it stays high."
                return base
            return "Your blood pressure is currently within a healthy range. Keep up your current habits!"
        return "I don't have a recent blood pressure reading yet. Please add it in Health Data Entry."

    # What to eat today
    if has("what should i eat", "eat today", "diet", "food"):
        b = ", ".join(diet_plan["breakfast"][:2])
        l = ", ".join(diet_plan["lunch"][:2])
        d = ", ".join(diet_plan["dinner"][:2])
        return f"Based on your health profile — Breakfast: {b}. Lunch: {l}. Dinner: {d}. Try to avoid: {', '.join(diet_plan['avoid'][:2])}."

    # Cholesterol
    if has("cholesterol"):
        chol_risk = risks.get("High Cholesterol", {})
        reasons = chol_risk.get("reasons", [])
        tip = "Reduce fried food and red meat, add more fiber (oats, vegetables), and exercise regularly."
        if reasons:
            return f"Your cholesterol risk factors include: {', '.join(reasons)}. {tip}"
        return f"Your cholesterol risk currently looks manageable. {tip}"

    # Health score decreasing / general score question
    if has("health score") and has("why", "decreas", "low", "drop"):
        weakest = min(
            [("Fitness", scores["fitness"]["score"]), ("Nutrition", scores["nutrition"]["score"]),
             ("Sleep", scores["sleep"]["score"]), ("Hydration", scores["hydration"]["score"]),
             ("Mental Wellness", scores["mental"]["score"])],
            key=lambda x: x[1],
        )
        reasons = scores[weakest[0].lower().split()[0]]["reasons"] if weakest[0].lower().split()[0] in scores else []
        msg = f"Your weakest area right now is {weakest[0]} ({weakest[1]}/100)."
        if reasons:
            msg += " Reason: " + "; ".join(reasons) + "."
        return msg

    # Exercise
    if has("exercise", "workout", "gym"):
        note = exercise_plan["note"]
        today_list = list(exercise_plan["weekly_schedule"].items())
        sample = "; ".join([f"{d}: {a}" for d, a in today_list[:3]])
        return f"{note}. Sample plan — {sample}. Check your Dashboard for the full weekly schedule."

    # Sleep
    if has("sleep"):
        return f"Your sleep score is {scores['sleep']['score']}/100. Aim for 7-9 hours nightly at a consistent time for the best recovery and mental wellness."

    # Overall health
    if has("overall", "how am i", "how is my health", "health status"):
        return f"Your overall health score is {scores['overall']}/100. Fitness: {scores['fitness']['score']}, Nutrition: {scores['nutrition']['score']}, Sleep: {scores['sleep']['score']}, Hydration: {scores['hydration']['score']}, Mental Wellness: {scores['mental']['score']}."

    # Weight / BMI
    if has("weight", "bmi", "fat"):
        bmi = profile.bmi
        if bmi:
            return f"Your current BMI is {bmi}. A healthy BMI range is 18.5-24.9. {exercise_plan['note']}"
        return "Please add your height and weight in your Health Profile so I can calculate your BMI."

    # Diabetes
    if has("diabetes", "sugar"):
        risk = risks.get("Diabetes", {})
        reasons = risk.get("reasons", [])
        msg = f"Your current diabetes risk is {risk.get('current', 'N/A')}%, projected to {risk.get('future', 'N/A')}% in 5 years if trends continue."
        if reasons:
            msg += " Key factors: " + "; ".join(reasons) + "."
        return msg

    # Fallback
    return (
        "I can help with questions about your blood pressure, sugar levels, cholesterol, "
        "diet, exercise, sleep, weight/BMI, or your overall health score. "
        "Try asking something like 'Why is my blood pressure high?' or 'What should I eat today?'"
    )
