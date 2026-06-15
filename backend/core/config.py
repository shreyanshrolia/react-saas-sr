"""Centralized configuration loaded from environment."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

JWT_SECRET = os.environ.get("JWT_SECRET", "grihkari-dev-secret-change-in-prod")
JWT_ALGO = "HS256"
JWT_EXP_DAYS = 30

TRIAL_DAYS = 45
IRON_PLAN_INR = 49
CLIENT_PLAN_INR = 19
SUBSCRIPTION_DAYS = 30

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
RAZORPAY_ENABLED = bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
HELPLINE_PHONE = "+91 63521 72550"

SECURITY_QUESTIONS = [
    "What is your mother's maiden name?",
    "What was the name of your first school?",
    "What is your favorite city?",
    "What is your pet's name?",
    "Who was your childhood best friend?",
]
