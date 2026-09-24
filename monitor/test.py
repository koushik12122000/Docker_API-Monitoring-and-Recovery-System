#!/usr/bin/env python3
"""Alert System Verification Script.

Tests Microsoft Graph API and Gmail SMTP connections without waiting for
service failure.
"""

from datetime import datetime
import config
from monitor import is_api_alive, send_gmail_email, send_ms_email_graph


def test_configuration():
    print("==========================================")
    print("Environment Configuration Diagnostic")
    print("==========================================")
    print(f"API Target URL:         {config.API_URL}")
    print(f"Target Container:       {config.CONTAINER_NAME}")
    print(f"Recipients:             {config.RECIPIENT_EMAILS or 'NOT CONFIGURED'}")
    print(f"Microsoft Client ID:    {'Configured' if config.CLIENT_ID else 'Not set'}")
    print(f"Microsoft Secret:       {'Configured' if config.CLIENT_SECRET else 'Not set'}")
    print(f"Microsoft Tenant:       {'Configured' if config.TENANT_ID else 'Not set'}")
    print(f"Gmail Sender:           {config.SENDER_EMAIL_GMAIL or 'Not set'}")
    print("==========================================\n")


def test_health_check():
    print("Testing API Health Check...")
    alive = is_api_alive()
    if alive:
        print("✅ API is reachable and responding with 200 OK.")
    else:
        print("❌ API is currently unreachable or returning an error.")


def test_send_alert():
    if not config.RECIPIENT_EMAILS:
        print("⚠️ No recipient configured in RECIPIENT_EMAILS. Skipping test email.")
        return

    recipient = config.RECIPIENT_EMAILS[0]
    subject = "🧪 Test Alert: Monitor Notification System Verification"
    body = f"""This is a test notification dispatched by the Docker Monitor verification script.

Timestamp: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
If you received this message, your alert notification pipeline is operating correctly.
"""
    print(f"\nSending test alert to {recipient}...")

    # Test Microsoft Graph
    if config.CLIENT_ID:
        print("Attempting Microsoft Graph API dispatch...")
        if send_ms_email_graph(recipient, subject, body):
            print("✅ Microsoft Graph alert sent successfully.")
        else:
            print("❌ Microsoft Graph dispatch failed.")

    # Test Gmail SMTP
    if config.SENDER_EMAIL_GMAIL and config.SENDER_PASSWORD_GMAIL:
        print("Attempting Gmail SMTP dispatch...")
        if send_gmail_email(recipient, subject, body):
            print("✅ Gmail SMTP alert sent successfully.")
        else:
            print("❌ Gmail SMTP dispatch failed.")


if __name__ == "__main__":
    test_configuration()
    test_health_check()

    choice = input("\nWould you like to send a test alert email to verify delivery? (y/N): ").strip().lower()
    if choice == "y":
        test_send_alert()