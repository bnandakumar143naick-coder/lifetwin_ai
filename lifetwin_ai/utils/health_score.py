"""
LifeTwin AI - Health Scoring Engine
------------------------------------
This is a transparent, explainable rule-based scoring system (not a black-box
model) so every score can show WHY it was given. Each sub-score is 0-100.
"""


def _clamp(value, low=0, high=100):
    return max(low, min(high, value))


def fitness_score(profile, vitals):
    score = 50
    reasons = []

    freq_map = {"None": -25, "1-2x week": 0, "3-5x week": 15, "Daily": 25}
    if profile.exercise_frequency in freq_map:
        score += freq_map[profile.exercise_frequency]
        reasons.append(f"Exercise frequency: {profile.exercise_frequency}")

    bmi = profile.bmi
    if bmi:
        if 18.5 <= bmi <= 24.9:
            score += 15
            reasons.append(f"BMI {bmi} is in the healthy range")
        elif 25 <= bmi <= 29.9:
            score -= 10
            reasons.append(f"BMI {bmi} is in the overweight range")
        elif bmi >= 30:
            score -= 20
            reasons.append(f"BMI {bmi} is in the obese range")
        elif bmi < 18.5:
            score -= 10
            reasons.append(f"BMI {bmi} is underweight")

    if vitals and vitals.heart_rate:
        if 60 <= vitals.heart_rate <= 100:
            score += 10
        else:
            score -= 10
            reasons.append(f"Resting heart rate {vitals.heart_rate} bpm is outside normal range")

    return _clamp(score), reasons


def nutrition_score(profile, labs):
    score = 60
    reasons = []

    if profile.water_intake_l:
        if profile.water_intake_l >= 2.0:
            score += 10
        else:
            score -= 10
            reasons.append(f"Water intake ({profile.water_intake_l} L/day) below recommended 2 L/day")

    if labs and labs.total_cholesterol:
        if labs.total_cholesterol < 200:
            score += 10
        else:
            score -= 15
            reasons.append(f"Total cholesterol {labs.total_cholesterol} mg/dL is elevated")

    if labs and labs.hba1c:
        if labs.hba1c < 5.7:
            score += 10
        elif labs.hba1c < 6.5:
            score -= 10
            reasons.append(f"HbA1c {labs.hba1c}% indicates prediabetes range")
        else:
            score -= 20
            reasons.append(f"HbA1c {labs.hba1c}% indicates diabetic range")

    if profile.smoking and profile.smoking != "Never":
        score -= 10
        reasons.append(f"Smoking status: {profile.smoking}")

    return _clamp(score), reasons


def sleep_score(profile):
    score = 50
    reasons = []
    if profile.sleep_hours:
        if 7 <= profile.sleep_hours <= 9:
            score = 90
            reasons.append(f"Sleep duration {profile.sleep_hours} hrs is optimal")
        elif 6 <= profile.sleep_hours < 7:
            score = 65
            reasons.append(f"Sleep duration {profile.sleep_hours} hrs is slightly low")
        else:
            score = 35
            reasons.append(f"Sleep duration {profile.sleep_hours} hrs is inadequate")
    return _clamp(score), reasons


def hydration_score(profile):
    score = 50
    reasons = []
    if profile.water_intake_l:
        if profile.water_intake_l >= 2.5:
            score = 95
        elif profile.water_intake_l >= 2.0:
            score = 80
        elif profile.water_intake_l >= 1.2:
            score = 55
            reasons.append("Water intake is below the ideal 2-3 L/day")
        else:
            score = 30
            reasons.append("Water intake is significantly low")
    return _clamp(score), reasons


def mental_wellness_score(profile):
    score = 70
    reasons = []
    stress_map = {"Low": 15, "Medium": -5, "High": -25}
    if profile.stress_level in stress_map:
        score += stress_map[profile.stress_level]
        reasons.append(f"Stress level reported: {profile.stress_level}")
    if profile.sleep_hours and profile.sleep_hours < 6:
        score -= 10
        reasons.append("Poor sleep is negatively affecting mental wellness")
    return _clamp(score), reasons


def compute_all_scores(profile, vitals, labs):
    fit, fit_r = fitness_score(profile, vitals)
    nut, nut_r = nutrition_score(profile, labs)
    sleep, sleep_r = sleep_score(profile)
    hyd, hyd_r = hydration_score(profile)
    mental, mental_r = mental_wellness_score(profile)

    overall = round((fit + nut + sleep + hyd + mental) / 5)

    return {
        "overall": overall,
        "fitness": {"score": fit, "reasons": fit_r},
        "nutrition": {"score": nut, "reasons": nut_r},
        "sleep": {"score": sleep, "reasons": sleep_r},
        "hydration": {"score": hyd, "reasons": hyd_r},
        "mental": {"score": mental, "reasons": mental_r},
    }
