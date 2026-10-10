import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "lifetwin-ai-dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "instance", "lifetwin.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REPORTS_DIR = os.path.join(BASE_DIR, "instance", "reports")
