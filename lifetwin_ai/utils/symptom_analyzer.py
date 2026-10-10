"""
LifeTwin AI - Symptom Analysis Engine
----------------------------------------
IMPORTANT: This is a rule-based educational tool. It NEVER provides a medical
diagnosis. It only surfaces possible related conditions, a risk level, and
whether a doctor visit is advisable. Always defaults to caution.
"""

# symptom -> (possible related conditions, base risk weight)
SYMPTOM_MAP = {
    "Headache": (["Tension / Stress", "Dehydration", "High Blood Pressure"], 1),
    "Fever": (["Viral Infection", "Bacterial Infection", "Flu"], 2),
    "Cough": (["Common Cold", "Respiratory Infection", "Asthma flare-up"], 1),
    "Chest Pain": (["Heart-related concern", "Acid Reflux", "Muscle Strain"], 4),
    "Stomach Pain": (["Indigestion", "Gastritis", "Food Intolerance"], 1),
    "Fatigue": (["Anemia", "Poor Sleep", "Thyroid Imbalance", "Diabetes"], 1),
    "Vomiting": (["Food Poisoning", "Gastritis", "Viral Infection"], 2),
    "Tooth Pain": (["Dental Cavity", "Gum Infection"], 1),
    "Skin Rash": (["Allergic Reaction", "Skin Infection"], 1),
    "Dizziness": (["Low Blood Pressure", "Dehydration", "Inner Ear Issue"], 2),
    "Shortness of Breath": (["Asthma", "Heart-related concern", "Anxiety"], 4),
}

HIGH_RISK_COMBOS = [
    ({"Chest Pain", "Shortness of Breath"}, "Combination of chest pain and breathlessness needs urgent evaluation"),
    ({"Fever", "Vomiting"}, "Persistent fever with vomiting can lead to dehydration"),
]


def analyze_symptoms(selected_symptoms, profile=None):
    if not selected_symptoms:
        return {"possible_conditions": [], "risk_level": "Low", "advice": [], "see_doctor": False}

    condition_set = set()
    weight = 0
    for s in selected_symptoms:
        conds, w = SYMPTOM_MAP.get(s, ([], 1))
        condition_set.update(conds)
        weight += w

    advice = []
    selected_set = set(selected_symptoms)
    for combo, msg in HIGH_RISK_COMBOS:
        if combo.issubset(selected_set):
            weight += 5
            advice.append(msg)

    if profile:
        if profile.hist_heart_disease and "Chest Pain" in selected_set:
            weight += 4
            advice.append("Existing heart condition makes chest pain more significant")
        if profile.hist_asthma and "Shortness of Breath" in selected_set:
            weight += 3
            advice.append("Existing asthma history — monitor breathing closely")

    if weight <= 3:
        risk_level = "Low"
        advice.append("Rest, stay hydrated, and monitor symptoms over the next 24-48 hours")
        see_doctor = False
    elif weight <= 7:
        risk_level = "Medium"
        advice.append("Consider consulting a doctor if symptoms persist beyond 2-3 days")
        see_doctor = False
    else:
        risk_level = "High"
        advice.append("Please consult a doctor promptly / seek medical attention")
        see_doctor = True

    return {
        "possible_conditions": sorted(condition_set),
        "risk_level": risk_level,
        "advice": advice,
        "see_doctor": see_doctor,
    }
