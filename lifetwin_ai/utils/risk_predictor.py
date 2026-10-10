"""
LifeTwin AI - Future Disease Risk Prediction Engine
-----------------------------------------------------
Explainable AI (XAI) style rule-based risk scoring. Each disease risk is
built from weighted factors (age, BMI, vitals, lab values, lifestyle,
family history) so the platform can show WHY a risk is high — exactly
what Module 8 in the spec requires.

current_risk = risk if no lifestyle change happens right now
future_risk  = projected risk in ~5 years if current trends continue
"""


def _pct(value):
    return max(1, min(97, round(value)))


def _age_factor(age):
    if age < 30:
        return 0
    if age < 40:
        return 5
    if age < 50:
        return 12
    if age < 60:
        return 20
    return 28


def predict_diabetes(profile, vitals, labs, age):
    score = 5 + _age_factor(age)
    reasons = []

    bmi = profile.bmi
    if bmi and bmi >= 30:
        score += 25; reasons.append("Obesity (BMI ≥ 30)")
    elif bmi and bmi >= 25:
        score += 12; reasons.append("Overweight BMI")

    if profile.hist_diabetes:
        score += 20; reasons.append("Personal history of diabetes")
    if profile.fam_diabetes:
        score += 15; reasons.append("Family history of diabetes")

    if vitals and vitals.blood_sugar:
        if vitals.blood_sugar >= 126:
            score += 25; reasons.append(f"Blood sugar {vitals.blood_sugar} mg/dL is in diabetic range")
        elif vitals.blood_sugar >= 100:
            score += 12; reasons.append(f"Blood sugar {vitals.blood_sugar} mg/dL is in prediabetic range")

    if labs and labs.hba1c:
        if labs.hba1c >= 6.5:
            score += 20; reasons.append(f"HbA1c {labs.hba1c}% indicates diabetes")
        elif labs.hba1c >= 5.7:
            score += 10; reasons.append(f"HbA1c {labs.hba1c}% indicates prediabetes")

    if profile.exercise_frequency == "None":
        score += 8; reasons.append("Sedentary lifestyle (no regular exercise)")

    current = _pct(score)
    future = _pct(score * 1.6)
    return current, future, reasons


def predict_hypertension(profile, vitals, age):
    score = 5 + _age_factor(age)
    reasons = []

    if vitals and vitals.systolic_bp and vitals.diastolic_bp:
        if vitals.systolic_bp >= 140 or vitals.diastolic_bp >= 90:
            score += 30; reasons.append(f"Blood pressure {vitals.systolic_bp}/{vitals.diastolic_bp} mmHg is high")
        elif vitals.systolic_bp >= 130 or vitals.diastolic_bp >= 85:
            score += 15; reasons.append(f"Blood pressure {vitals.systolic_bp}/{vitals.diastolic_bp} mmHg is elevated")

    if profile.hist_hypertension:
        score += 20; reasons.append("Personal history of hypertension")

    bmi = profile.bmi
    if bmi and bmi >= 30:
        score += 15; reasons.append("Obesity increases hypertension risk")

    if profile.stress_level == "High":
        score += 10; reasons.append("High reported stress level")
    if profile.smoking and profile.smoking != "Never":
        score += 8; reasons.append("Smoking habit")
    if profile.alcohol == "Regular":
        score += 7; reasons.append("Regular alcohol consumption")

    current = _pct(score)
    future = _pct(score * 1.5)
    return current, future, reasons


def predict_heart_disease(profile, vitals, labs, age):
    score = 3 + _age_factor(age)
    reasons = []

    if profile.hist_heart_disease:
        score += 25; reasons.append("Personal history of heart disease")
    if profile.fam_heart_disease:
        score += 18; reasons.append("Family history of heart disease")
    if profile.hist_hypertension:
        score += 10; reasons.append("Existing hypertension")
    if profile.smoking and profile.smoking != "Never":
        score += 15; reasons.append("Smoking habit")

    if labs and labs.total_cholesterol and labs.total_cholesterol >= 240:
        score += 18; reasons.append(f"High total cholesterol ({labs.total_cholesterol} mg/dL)")
    elif labs and labs.total_cholesterol and labs.total_cholesterol >= 200:
        score += 8; reasons.append(f"Borderline cholesterol ({labs.total_cholesterol} mg/dL)")

    bmi = profile.bmi
    if bmi and bmi >= 30:
        score += 10; reasons.append("Obesity is a cardiovascular risk factor")

    if profile.exercise_frequency == "None":
        score += 8; reasons.append("Lack of physical activity")

    current = _pct(score)
    future = _pct(score * 1.55)
    return current, future, reasons


def predict_stroke(profile, vitals, age):
    score = 2 + _age_factor(age)
    reasons = []

    if profile.fam_stroke:
        score += 18; reasons.append("Family history of stroke")
    if profile.hist_hypertension or (vitals and vitals.systolic_bp and vitals.systolic_bp >= 140):
        score += 20; reasons.append("Uncontrolled/history of high blood pressure")
    if profile.smoking and profile.smoking != "Never":
        score += 12; reasons.append("Smoking habit")
    if profile.hist_diabetes:
        score += 10; reasons.append("Existing diabetes")

    current = _pct(score)
    future = _pct(score * 1.5)
    return current, future, reasons


def predict_kidney_disease(profile, vitals, labs, age):
    score = 3 + _age_factor(age)
    reasons = []

    if profile.hist_kidney_disease:
        score += 25; reasons.append("Personal history of kidney disease")
    if profile.fam_kidney_disease:
        score += 15; reasons.append("Family history of kidney disease")
    if profile.hist_diabetes or profile.hist_hypertension:
        score += 15; reasons.append("Diabetes/hypertension increase kidney strain")

    if labs and labs.creatinine and labs.creatinine > 1.3:
        score += 20; reasons.append(f"Elevated creatinine ({labs.creatinine} mg/dL)")
    if labs and labs.kidney_egfr and labs.kidney_egfr < 60:
        score += 20; reasons.append(f"Low eGFR ({labs.kidney_egfr}) indicates reduced kidney function")

    current = _pct(score)
    future = _pct(score * 1.4)
    return current, future, reasons


def predict_fatty_liver(profile, labs, age):
    score = 5 + _age_factor(age) * 0.6
    reasons = []
    bmi = profile.bmi
    if bmi and bmi >= 30:
        score += 25; reasons.append("Obesity strongly linked to fatty liver")
    elif bmi and bmi >= 25:
        score += 12; reasons.append("Overweight increases fatty liver risk")
    if profile.alcohol == "Regular":
        score += 15; reasons.append("Regular alcohol consumption")
    if labs and labs.liver_alt and labs.liver_alt > 40:
        score += 20; reasons.append(f"Elevated liver ALT ({labs.liver_alt} U/L)")
    if profile.hist_diabetes:
        score += 10; reasons.append("Diabetes increases fatty liver risk")

    current = _pct(score)
    future = _pct(score * 1.4)
    return current, future, reasons


def predict_obesity(profile, age):
    score = 5
    reasons = []
    bmi = profile.bmi
    if bmi:
        if bmi >= 30:
            score += 55; reasons.append(f"Current BMI {bmi} already in obese range")
        elif bmi >= 25:
            score += 30; reasons.append(f"Current BMI {bmi} in overweight range, trending toward obesity")
    if profile.exercise_frequency == "None":
        score += 15; reasons.append("No regular physical activity")
    if profile.water_intake_l and profile.water_intake_l < 1.5:
        score += 5

    current = _pct(score)
    future = _pct(score * 1.2)
    return current, future, reasons


def predict_high_cholesterol(profile, labs, age):
    score = 5 + _age_factor(age) * 0.8
    reasons = []
    if labs and labs.total_cholesterol:
        if labs.total_cholesterol >= 240:
            score += 40; reasons.append(f"Total cholesterol {labs.total_cholesterol} mg/dL is high")
        elif labs.total_cholesterol >= 200:
            score += 20; reasons.append(f"Total cholesterol {labs.total_cholesterol} mg/dL is borderline high")
    bmi = profile.bmi
    if bmi and bmi >= 25:
        score += 10; reasons.append("Elevated BMI contributes to high cholesterol")
    if profile.exercise_frequency == "None":
        score += 8; reasons.append("Sedentary lifestyle")

    current = _pct(score)
    future = _pct(score * 1.35)
    return current, future, reasons


def predict_thyroid_disorder(profile, age):
    score = 8 + _age_factor(age) * 0.5
    reasons = []
    if profile.hist_thyroid:
        score += 35; reasons.append("Personal history of thyroid disease")
    current = _pct(score)
    future = _pct(score * 1.2)
    return current, future, reasons


def predict_arthritis(profile, age):
    score = 2 + _age_factor(age) * 1.1
    reasons = []
    bmi = profile.bmi
    if bmi and bmi >= 30:
        score += 15; reasons.append("Excess weight adds stress on joints")
    if age >= 50:
        reasons.append("Age is the strongest risk factor for arthritis")
    current = _pct(score)
    future = _pct(score * 1.3)
    return current, future, reasons


def predict_all_risks(user, profile, vitals, labs):
    age = user.age
    results = {}

    d_c, d_f, d_r = predict_diabetes(profile, vitals, labs, age)
    h_c, h_f, h_r = predict_hypertension(profile, vitals, age)
    hd_c, hd_f, hd_r = predict_heart_disease(profile, vitals, labs, age)
    s_c, s_f, s_r = predict_stroke(profile, vitals, age)
    k_c, k_f, k_r = predict_kidney_disease(profile, vitals, labs, age)
    fl_c, fl_f, fl_r = predict_fatty_liver(profile, labs, age)
    ob_c, ob_f, ob_r = predict_obesity(profile, age)
    ch_c, ch_f, ch_r = predict_high_cholesterol(profile, labs, age)
    th_c, th_f, th_r = predict_thyroid_disorder(profile, age)
    ar_c, ar_f, ar_r = predict_arthritis(profile, age)

    results["Diabetes"] = {"current": d_c, "future": d_f, "reasons": d_r}
    results["Hypertension"] = {"current": h_c, "future": h_f, "reasons": h_r}
    results["Heart Disease"] = {"current": hd_c, "future": hd_f, "reasons": hd_r}
    results["Stroke"] = {"current": s_c, "future": s_f, "reasons": s_r}
    results["Kidney Disease"] = {"current": k_c, "future": k_f, "reasons": k_r}
    results["Fatty Liver Disease"] = {"current": fl_c, "future": fl_f, "reasons": fl_r}
    results["Obesity"] = {"current": ob_c, "future": ob_f, "reasons": ob_r}
    results["High Cholesterol"] = {"current": ch_c, "future": ch_f, "reasons": ch_r}
    results["Thyroid Disorders"] = {"current": th_c, "future": th_f, "reasons": th_r}
    results["Arthritis"] = {"current": ar_c, "future": ar_f, "reasons": ar_r}

    return results
