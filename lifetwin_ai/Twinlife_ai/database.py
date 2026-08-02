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
