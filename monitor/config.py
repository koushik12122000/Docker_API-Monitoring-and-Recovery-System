"""Configuration settings for Docker Container & API Monitor.
All settings are loaded securely from environment variables.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Search for .env in current folder or parent folder
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
PARENT_ENV_PATH = BASE_DIR.parent / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
elif PARENT_ENV_PATH.exists():
    load_dotenv(dotenv_path=PARENT_ENV_PATH)
else:
    load_dotenv()

# ==========================================
# Target Service & Health Check
# ==========================================
API_URL = os.getenv("API_URL", "http://localhost:8000/general/v0/general")
CONTAINER_NAME = os.getenv("CONTAINER_NAME", "unstructured-api")
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY_SECONDS = int(os.getenv("RETRY_DELAY_SECONDS", "15"))
LOG_FILE = os.getenv("LOG_FILE", "api_monitor.log")

# ==========================================
# Alert Throttling & Cooldown
# ==========================================
MAX_ALERTS = int(os.getenv("MAX_ALERTS", "5"))
ALERT_COOLDOWN = int(os.getenv("ALERT_COOLDOWN_SECONDS", "200"))

# ==========================================
# Recipients
# ==========================================
_raw_recipients = os.getenv("RECIPIENT_EMAILS") or os.getenv("RECIPIENT_EMAIL") or ""
RECIPIENT_EMAILS = [r.strip() for r in _raw_recipients.split(",") if r.strip()]
RECIPIENT_EMAIL = RECIPIENT_EMAILS[0] if RECIPIENT_EMAILS else ""

# ==========================================
# Microsoft Graph API Configuration
# ==========================================
SENDER_EMAIL_MS = os.getenv("SENDER_EMAIL_MS", "")
CLIENT_ID = os.getenv("CLIENT_ID", "")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
TENANT_ID = os.getenv("TENANT_ID", "")
AUTHORITY = (
    f"https://login.microsoftonline.com/{TENANT_ID}"
    if TENANT_ID
    else "https://login.microsoftonline.com/common"
)
SCOPES = ["https://graph.microsoft.com/.default"] if CLIENT_SECRET else ["https://graph.microsoft.com/Mail.Send"]

# ==========================================
# Gmail SMTP Configuration (Alternative / Fallback)
# ==========================================
SMTP_SERVER_GMAIL = os.getenv("SMTP_SERVER_GMAIL", "smtp.gmail.com")
SMTP_PORT_GMAIL = int(os.getenv("SMTP_PORT_GMAIL", "587"))
SENDER_EMAIL_GMAIL = os.getenv("SENDER_EMAIL_GMAIL", "")
SENDER_PASSWORD_GMAIL = os.getenv("SENDER_PASSWORD_GMAIL", "")
