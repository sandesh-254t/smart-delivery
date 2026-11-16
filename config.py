import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///smart_delivery.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DELHIVERY_ENABLED = os.getenv("DELHIVERY_ENABLED", "0") == "1"
    DELHIVERY_API_TOKEN = os.getenv("DELHIVERY_API_TOKEN", "")
    DELHIVERY_BASE_URL = os.getenv("DELHIVERY_BASE_URL", "").rstrip("/")
    DELHIVERY_TRACKING_PATH = os.getenv("DELHIVERY_TRACKING_PATH", "")
