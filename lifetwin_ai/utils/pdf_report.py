import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)


def generate_pdf_report(path, user, profile, vitals, symptoms_result, scores, risks, diet_plan, exercise_plan, preventive_care):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleX", parent=styles["Title"], textColor=colors.HexColor("#0f766e"))
    h2 = ParagraphStyle("H2X", parent=styles["Heading2"], textColor=colors.HexColor("#0f766e"), spaceBefore=14)
    normal = styles["Normal"]

    story = []
    story.append(Paragraph("LifeTwin AI — Digital Health Twin Report", title_style))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%d %b %Y, %I:%M %p')}", normal))
    story.append(Spacer(1, 12))

    # Personal Info
    story.append(Paragraph("Personal Information", h2))
    info_data = [
        ["Name", user.full_name, "Age", str(user.age)],
        ["Gender", user.gender, "BMI", str(profile.bmi or "N/A")],
    ]
    t = Table(info_data, colWidths=[3 * cm, 5 * cm, 3 * cm, 5 * cm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e0f2f1")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#e0f2f1")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(t)

    # Health Scores
    story.append(Paragraph("Health Scores", h2))
    score_data = [["Metric", "Score (0-100)"]]
    for label, key in [("Overall", "overall"), ("Fitness", "fitness"), ("Nutrition", "nutrition"),
                        ("Sleep", "sleep"), ("Hydration", "hydration"), ("Mental Wellness", "mental")]:
        val = scores["overall"] if key == "overall" else scores[key]["score"]
        score_data.append([label, str(val)])
    t2 = Table(score_data, colWidths=[8 * cm, 8 * cm])
    t2.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(t2)

    # Vitals
    if vitals:
        story.append(Paragraph("Latest Vital Signs", h2))
        vdata = [
            ["Blood Pressure", f"{vitals.systolic_bp or '-'}/{vitals.diastolic_bp or '-'} mmHg"],
            ["Blood Sugar", f"{vitals.blood_sugar or '-'} mg/dL"],
            ["Heart Rate", f"{vitals.heart_rate or '-'} bpm"],
            ["Oxygen Saturation", f"{vitals.oxygen_saturation or '-'} %"],
            ["Body Temperature", f"{vitals.body_temperature or '-'} °C"],
        ]
        t3 = Table(vdata, colWidths=[8 * cm, 8 * cm])
        t3.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
        story.append(t3)

    # Symptom Analysis
    story.append(Paragraph("Symptom Analysis", h2))
    if symptoms_result and symptoms_result.get("possible_conditions"):
        story.append(Paragraph(f"Risk Level: <b>{symptoms_result['risk_level']}</b>", normal))
        story.append(Paragraph("Possible related conditions (not a diagnosis): " + ", ".join(symptoms_result["possible_conditions"]), normal))
        for a in symptoms_result["advice"]:
            story.append(Paragraph("• " + a, normal))
    else:
        story.append(Paragraph("No current symptoms reported.", normal))

    # Disease Risk Predictions
    story.append(Paragraph("Future Disease Risk Predictions", h2))
    rdata = [["Disease", "Current Risk", "Future Risk (~5 yrs)"]]
    for disease, r in risks.items():
        rdata.append([disease, f"{r['current']}%", f"{r['future']}%"])
    t4 = Table(rdata, colWidths=[7 * cm, 4.5 * cm, 4.5 * cm])
    t4.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(t4)

    story.append(PageBreak())

    # Diet plan
    story.append(Paragraph("Personalized Diet Plan", h2))
    for meal, items in [("Breakfast", diet_plan["breakfast"]), ("Lunch", diet_plan["lunch"]),
                         ("Dinner", diet_plan["dinner"]), ("Snacks", diet_plan["snacks"])]:
        story.append(Paragraph(f"<b>{meal}:</b> " + ", ".join(items), normal))
    story.append(Paragraph(f"<b>Water Target:</b> {diet_plan['water_target_l']} L/day", normal))
    story.append(Paragraph("<b>Foods to Avoid:</b> " + ", ".join(diet_plan["avoid"]), normal))

    # Exercise plan
    story.append(Paragraph("Exercise Plan", h2))
    story.append(Paragraph(exercise_plan["note"], normal))
    ex_data = [[d, a] for d, a in exercise_plan["weekly_schedule"].items()]
    t5 = Table([["Day", "Activity"]] + ex_data, colWidths=[4 * cm, 12 * cm])
    t5.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    story.append(t5)

    # Preventive care
    story.append(Paragraph("Preventive Care Reminders", h2))
    for item in preventive_care:
        story.append(Paragraph("• " + item, normal))

    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "<i>Disclaimer: LifeTwin AI provides AI-generated wellness insights for preventive awareness only. "
        "It is not a substitute for professional medical diagnosis or treatment. Please consult a licensed "
        "doctor for medical decisions.</i>", normal))

    doc.build(story)
    return path
