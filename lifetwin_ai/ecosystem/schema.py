"""
In-place, non-destructive schema upgrade.

db.create_all() creates NEW tables but never adds columns to an existing table.
The only change to an ORIGINAL table is two additive columns on `users`.
Existing rows automatically become role = PATIENT. Nothing is dropped or rewritten.
"""
from sqlalchemy import inspect, text


def ensure_ecosystem_schema(db):
    inspector = inspect(db.engine)
    if "users" not in inspector.get_table_names():
        return  # fresh DB: create_all() already built the full schema
    existing = {c["name"] for c in inspector.get_columns("users")}

    with db.engine.begin() as conn:
        if "role" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'PATIENT'"))
        if "phone" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(30)"))
        # Defensive backfill: anything without a role is a legacy patient.
        conn.execute(text("UPDATE users SET role = 'PATIENT' WHERE role IS NULL OR role = ''"))
