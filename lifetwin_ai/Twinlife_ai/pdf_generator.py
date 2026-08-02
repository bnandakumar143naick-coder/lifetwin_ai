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
