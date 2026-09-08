import os
import sys
import time
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

LOGIN_URL = "https://silverlake.onlinecourtreservations.com/reservations"
USERNAME = os.environ.get("PORTAL_USER")
PASSWORD = os.environ.get("PORTAL_PASS")

# Email Configuration Setup
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465

RECIPIENT_EMAILS = ["atjbernardo@gmail.com", "nalvior@hotmail.com"]


def get_next_tuesday():
    today = datetime.now()
    # Python's weekday(): Monday is 0, Tuesday is 1, Wednesday is 2...
    days_until_tuesday = (1 - today.weekday()) % 7
    if days_until_tuesday == 0:
        days_until_tuesday = 7
    next_tuesday = today + timedelta(days=days_until_tuesday)
    return f"{next_tuesday.month}/{next_tuesday.day}/{next_tuesday.year}"


def send_email(subject, body):
    """Utility to send an email notification."""
    if not SMTP_USER or not SMTP_PASS:
        print("⚠️ Email credentials (SMTP_USER / SMTP_PASS) not found. Skipping email notification.")
        return

    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = SMTP_USER
    msg['To'] = ", ".join(RECIPIENT_EMAILS)

    try:
        # Create a secure SSL context
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"📧 Email notification successfully sent to: {msg['To']}")
    except Exception as e:
        print(f"❌ Failed to send email. Error: {e}")


def write_github_summary(markdown_text):
    """Utility to write output directly to the GitHub Actions Job Summary tab."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(markdown_text + "\n")


def run():
    with sync_playwright() as p:
        # Running headless (invisible) for GitHub Actions
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Navigating to main reservations page...")
        page.goto(LOGIN_URL)

        print("Navigating to sign-in page...")
        page.evaluate("frmCalendar.action = 'SignIn'; frmCalendar.submit();")
        page.wait_for_load_state("networkidle")

        print("Filling credentials...")
        page.type("#user_id", USERNAME, delay=50)
        page.type("#password", PASSWORD, delay=50)

        print("Submitting login form...")
        page.click("#CheckUser")
        page.wait_for_load_state("networkidle")

        target_date = get_next_tuesday()
        print(f"Targeting next Tuesday: {target_date}")

        print("Opening reservation form for Court 1 at 9:00 AM...")
        # 19 represents 9:00 AM in the system's dropdown values
        with page.expect_navigation():
            page.evaluate(f"Reserve_Single('1', '19', '{target_date}');")

        print("Populating reservation form fields...")
        page.select_option("#Court_Num", "1")  # Tennis 1/PB 1
        page.select_option("#Start_Time", "19")  # 9:00 AM
        page.select_option("#Duration", "3")  # 1 hour 30 minutes
        page.select_option("#Hybrid", "P")  # Pickleball

        page.select_option("#Reservation_Type", "P")  # Pickle Ball
        page.dispatch_event("#Reservation_Type", "change")

        page.select_option("#Player_2", "Guest")
        page.select_option("#Player_3", "Guest")
        page.select_option("#Player_4", "Guest")

        print("Submitting reservation...")
        page.click("#SaveReservation")
        page.wait_for_load_state("networkidle")

        # Allow time for error alerts or confirmation page to load
        time.sleep(2)

        # Retrieve text from the page body
        page_text = page.inner_text("body").lower()

        # Check for error messages returned by onlinecourtreservations
        failure_keywords = [
            "already reserved",
            "conflict",
            "unavailable",
            "error",
            "cannot reserve",
            "exceeds limit",
        ]
        has_error = any(keyword in page_text for keyword in failure_keywords)

        if has_error:
            print("❌ ERROR: Reservation failed! Slot is unavailable or taken.")
            
            # Save screenshot for debugging
            page.screenshot(path="booking_failure.png", full_page=True)

            # GitHub Summary
            summary_text = (
                f"### ❌ TEST Court Booking Failed\n"
                f"* **Target Date:** {target_date} (Tuesday)\n"
                f"* **Time:** 9:00 AM (Court 1)\n"
                f"* **Reason:** Time slot was unavailable, already reserved, or returned an error."
            )
            write_github_summary(summary_text)

            # Send Failure Email
            send_email(
                subject=f"❌ Pickleball Court Booking Failed ({target_date})",
                body=f"Hello,\n\nThe automated script failed to book the Pickleball court for Tuesday, {target_date} at 9:00 AM.\n\nThe time slot may have already been taken by someone else or the system returned an error."
            )

            browser.close()
            # Force GitHub Actions to fail (Red ❌)
            sys.exit(1)

        else:
            print("✅ Reservation completed successfully!")
            
            # GitHub Summary
            summary_text = (
                f"### ✅ TEST Court Booking Successful!\n"
                f"* **Target Date:** {target_date} (Tuesday)\n"
                f"* **Time:** 9:00 AM (Court 1)\n"
                f"* **Type:** Pickleball"
            )
            write_github_summary(summary_text)

            # Send Success Email
            send_email(
                subject=f"✅ Pickleball Court Booked! ({target_date})",
                body=f"Hello,\n\nGreat news! The automated script successfully booked the Pickleball court for Tuesday, {target_date} at 9:00 AM (Court 1).\n\nIMPORTANT: Since this was a test, please log in and manually cancel this reservation if you do not actually intend to play at this time."
            )

        browser.close()


if __name__ == "__main__":
    run()
