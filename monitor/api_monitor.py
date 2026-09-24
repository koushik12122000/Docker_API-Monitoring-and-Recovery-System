#!/usr/bin/env python3
"""Lightweight API Health Monitor (SMTP).

Performs health check on target service, restarts container if unhealthy,
and dispatches SMTP alerts.
"""

import subprocess
import time
from datetime import datetime
from email.mime.text import MIMEText
import smtplib
import requests

import config


def log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    print(formatted)
    try:
        with open(config.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception as e:
        print(f"File log error: {e}")


def is_api_alive() -> bool:
    try:
        files = {"files": ("dummy.txt", b"healthcheck")}
        response = requests.post(config.API_URL, files=files, timeout=10)
        return response.status_code == 200
    except Exception as e:
        log(f"Health check failed: {e}")
        return False


def restart_container() -> bool:
    try:
        subprocess.run(["docker", "restart", config.CONTAINER_NAME], check=True)
        log(f"Restarted container: {config.CONTAINER_NAME}")
        return True
    except subprocess.CalledProcessError as e:
        log(f"Failed to restart container: {e}")
        return False


def send_email(smtp_server, smtp_port, sender_email, sender_password, recipient_email, subject, body):
    if not sender_email or not sender_password or not recipient_email:
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        log(f"Failed to send email from {sender_email}: {e}")
        return False


def send_alert_email() -> None:
    subject = f"⚠️ Service Failure Alert [{config.CONTAINER_NAME}]"
    body = f"""The target service failed to respond after container restart attempts.
Endpoint: {config.API_URL}
Container: {config.CONTAINER_NAME}
Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Please inspect server logs immediately.
"""
    for recipient in config.RECIPIENT_EMAILS:
        if config.SENDER_EMAIL_GMAIL and config.SENDER_PASSWORD_GMAIL:
            if send_email(
                config.SMTP_SERVER_GMAIL,
                config.SMTP_PORT_GMAIL,
                config.SENDER_EMAIL_GMAIL,
                config.SENDER_PASSWORD_GMAIL,
                recipient,
                subject,
                body,
            ):
                log(f"SMTP alert sent to {recipient}.")


def main() -> None:
    log("Running API health check...")
    for attempt in range(config.MAX_RETRIES):
        if is_api_alive():
            log("API is healthy.")
            return

        log(f"API is DOWN! Attempting restart... (Attempt {attempt + 1}/{config.MAX_RETRIES})")
        restart_container()
        time.sleep(config.RETRY_DELAY_SECONDS)

    if is_api_alive():
        log("API is back online after restart.")
    else:
        log("API FAILED after retries. Sending alert emails...")
        send_alert_email()


if __name__ == "__main__":
    main()
