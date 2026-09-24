#!/usr/bin/env python3
"""Docker Container & API Health Monitor.

Continuously monitors target API endpoints, triggers automated container
restarts on failure, and dispatches rate-limited alerts via Microsoft Graph API
and SMTP.
"""

import os
import subprocess
import time
from datetime import datetime
from email.mime.text import MIMEText
import smtplib
import requests
import msal

import config

# State tracking for rate limiting & deduplication
alerts_sent = 0
last_alert_time = None


def log(message: str) -> None:
    """Logs message with timestamp to console and configured log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {message}"
    print(formatted_msg)
    try:
        with open(config.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted_msg + "\n")
    except Exception as e:
        print(f"[{timestamp}] Logging to file failed: {e}")


def is_api_alive() -> bool:
    """Performs a health check against the target API endpoint."""
    try:
        # POST with dummy payload suitable for document processing endpoints (e.g. Unstructured)
        files = {"files": ("healthcheck.txt", b"ping")}
        response = requests.post(config.API_URL, files=files, timeout=10)
        return response.status_code == 200
    except Exception as e:
        log(f"Health check failed: {e}")
        return False


def restart_container() -> bool:
    """Restarts target Docker container via Docker CLI."""
    try:
        result = subprocess.run(
            ["docker", "restart", config.CONTAINER_NAME],
            check=True,
            capture_output=True,
            text=True,
        )
        log(f"Successfully restarted container: {config.CONTAINER_NAME}")
        return True
    except subprocess.CalledProcessError as e:
        log(f"Failed to restart container {config.CONTAINER_NAME}: {e.stderr.strip() if e.stderr else e}")
        return False
    except FileNotFoundError:
        log("Docker executable not found. Ensure Docker is installed and in PATH.")
        return False


def send_gmail_email(recipient_email: str, subject: str, body: str) -> bool:
    """Sends an email alert using Gmail SMTP."""
    if not config.SENDER_EMAIL_GMAIL or not config.SENDER_PASSWORD_GMAIL:
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = config.SENDER_EMAIL_GMAIL
    msg["To"] = recipient_email

    try:
        server = smtplib.SMTP(config.SMTP_SERVER_GMAIL, config.SMTP_PORT_GMAIL)
        server.starttls()
        server.login(config.SENDER_EMAIL_GMAIL, config.SENDER_PASSWORD_GMAIL)
        server.sendmail(config.SENDER_EMAIL_GMAIL, recipient_email, msg.as_string())
        server.quit()
        log(f"Gmail alert delivered to {recipient_email}.")
        return True
    except Exception as e:
        log(f"Failed to send Gmail alert: {e}")
        return False


def get_ms_access_token() -> str | None:
    """Acquires OAuth2 token for Microsoft Graph API.
    
    Supports unattended daemon auth (Client Secret) or Device Code Flow.
    """
    if not config.CLIENT_ID:
        return None

    # Unattended Daemon Application flow (preferred for automated server monitoring)
    if config.CLIENT_SECRET:
        app = msal.ConfidentialClientApplication(
            client_id=config.CLIENT_ID,
            authority=config.AUTHORITY,
            client_credential=config.CLIENT_SECRET,
        )
        result = app.acquire_token_for_client(scopes=config.SCOPES)
        if "access_token" in result:
            return result["access_token"]
        log(f"MS daemon auth failed: {result.get('error_description')}")
        return None

    # Fallback: Public Client application with Device Code Flow
    app = msal.PublicClientApplication(config.CLIENT_ID, authority=config.AUTHORITY)
    accounts = app.get_accounts()
    result = app.acquire_token_silent(config.SCOPES, account=accounts[0] if accounts else None)
    if result and "access_token" in result:
        return result["access_token"]

    flow = app.initiate_device_flow(config.SCOPES)
    if "error" in flow:
        log(f"MS device flow init failed: {flow.get('error_description')}")
        return None

    print(flow["message"])
    result = app.acquire_token_by_device_flow(flow)
    if "access_token" in result:
        return result["access_token"]

    log(f"MS auth failed: {result.get('error_description')}")
    return None


def send_ms_email_graph(recipient_email: str, subject: str, body: str) -> bool:
    """Sends an email alert using Microsoft Graph API."""
    token = get_ms_access_token()
    if not token:
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    email_message = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": recipient_email}}],
        },
        "saveToSentItems": "true",
    }

    # Endpoint differs if authenticating as a specific service principal vs interactive user
    if config.CLIENT_SECRET and config.SENDER_EMAIL_MS:
        url = f"https://graph.microsoft.com/v1.0/users/{config.SENDER_EMAIL_MS}/sendMail"
    else:
        url = "https://graph.microsoft.com/v1.0/me/sendMail"

    try:
        response = requests.post(url, headers=headers, json=email_message, timeout=15)
        if response.status_code == 202:
            log(f"Microsoft Graph alert delivered to {recipient_email}.")
            return True
        log(f"Microsoft Graph send failed: HTTP {response.status_code} - {response.text}")
        return False
    except Exception as e:
        log(f"Microsoft Graph request failed: {e}")
        return False


def send_alert_email() -> bool:
    """Dispatches failure alerts across configured channels with rate limiting."""
    global alerts_sent, last_alert_time

    current_time = time.time()
    can_send = (
        alerts_sent < config.MAX_ALERTS
        and (last_alert_time is None or current_time - last_alert_time >= config.ALERT_COOLDOWN)
    )

    if not can_send:
        if alerts_sent >= config.MAX_ALERTS:
            log(f"Alert suppressed: Maximum threshold ({config.MAX_ALERTS}) reached.")
        else:
            remaining = int(config.ALERT_COOLDOWN - (current_time - (last_alert_time or 0)))
            log(f"Alert suppressed: Cooldown active ({remaining}s remaining).")
        return False

    subject = f"⚠️ Alert: Container Failure Detected [{config.CONTAINER_NAME}]"
    body = f"""ALERT: API Service Failure Notification
------------------------------------------------
The service endpoint failed to respond successfully even after container restart attempts.

Container Target: {config.CONTAINER_NAME}
API Endpoint:     {config.API_URL}
Timestamp:        {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Alert Count:      {alerts_sent + 1} / {config.MAX_ALERTS}

Action Required:
Please inspect server system resources, container runtime logs, and network connectivity.
"""
    recipients = config.RECIPIENT_EMAILS
    if not recipients:
        log("No recipients configured in RECIPIENT_EMAILS or RECIPIENT_EMAIL.")
        return False

    dispatched = False
    for recipient in recipients:
        ms_sent = send_ms_email_graph(recipient, subject, body)
        gmail_sent = send_gmail_email(recipient, subject, body)
        if ms_sent or gmail_sent:
            dispatched = True

    if dispatched:
        alerts_sent += 1
        last_alert_time = current_time
        log(f"Alert #{alerts_sent} dispatched successfully.")
        return True

    log("Failed to dispatch alert across any channel. Check configuration.")
    return False


def run_check_cycle() -> None:
    """Executes single health check cycle with automatic restart retries."""
    log("Running service health check...")
    for attempt in range(config.MAX_RETRIES + 1):
        if is_api_alive():
            log("Service is healthy and responding.")
            return

        if attempt < config.MAX_RETRIES:
            log(f"Service unreachable! Attempting container restart ({attempt + 1}/{config.MAX_RETRIES})...")
            restart_container()
            time.sleep(config.RETRY_DELAY_SECONDS)
        else:
            log("Service remains DOWN after maximum restart attempts. Initiating alert flow...")
            send_alert_email()


def main() -> None:
    """Main daemon loop."""
    log(f"Starting API Monitor for container '{config.CONTAINER_NAME}' (Interval: {config.CHECK_INTERVAL_SECONDS}s)")
    while True:
        try:
            run_check_cycle()
        except KeyboardInterrupt:
            log("Monitor daemon stopped by user.")
            break
        except Exception as e:
            log(f"Unexpected monitor error: {e}")
        time.sleep(config.CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()