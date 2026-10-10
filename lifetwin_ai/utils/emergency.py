"""
LifeTwin AI - Emergency Detection Engine
------------------------------------------
Checks the latest vital signs against clinically recognized dangerous
thresholds and raises alerts. This is a safety net, not a diagnosis.
"""


def check_emergency(vitals):
    alerts = []
    if not vitals:
        return alerts

    if vitals.systolic_bp and vitals.systolic_bp >= 180:
        alerts.append(f"Extremely high blood pressure ({vitals.systolic_bp} systolic) — hypertensive crisis risk")
    if vitals.diastolic_bp and vitals.diastolic_bp >= 120:
        alerts.append(f"Extremely high diastolic blood pressure ({vitals.diastolic_bp})")

    if vitals.blood_sugar:
        if vitals.blood_sugar >= 300:
            alerts.append(f"Very high blood sugar ({vitals.blood_sugar} mg/dL) — risk of hyperglycemic emergency")
        elif vitals.blood_sugar <= 60:
            alerts.append(f"Very low blood sugar ({vitals.blood_sugar} mg/dL) — risk of hypoglycemia")

    if vitals.oxygen_saturation and vitals.oxygen_saturation < 90:
        alerts.append(f"Very low oxygen saturation ({vitals.oxygen_saturation}%) — seek immediate care")

    if vitals.heart_rate:
        if vitals.heart_rate >= 130:
            alerts.append(f"Very high heart rate ({vitals.heart_rate} bpm)")
        elif vitals.heart_rate <= 40:
            alerts.append(f"Very low heart rate ({vitals.heart_rate} bpm)")

    if vitals.body_temperature and vitals.body_temperature >= 40:
        alerts.append(f"Dangerously high body temperature ({vitals.body_temperature}°C)")

    return alerts
