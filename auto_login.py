import os
import sys
import time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

LOGIN_URL = "https://silverlake.onlinecourtreservations.com/reservations"
USERNAME = os.environ.get("PORTAL_USER")
PASSWORD = os.environ.get("PORTAL_PASS")


def get_next_monday():
    today = datetime.now()
    days_until_monday = (0 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    next_monday = today + timedelta(days=days_until_monday)
    return f"{next_monday.month}/{next_monday.day}/{next_monday.year}"


def write_github_summary(markdown_text):
    """Utility to write output directly to the GitHub Actions Job Summary tab."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(markdown_text + "\n")


def run():
    with sync_playwright() as p:
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

        target_date = get_next_monday()
        print(f"Targeting next Monday: {target_date}")

        print("Opening reservation form for Court 1 at 8:00 PM...")
        with page.expect_navigation():
            page.evaluate(f"Reserve_Single('1', '41', '{target_date}');")

        print("Populating reservation form fields...")
        page.select_option("#Court_Num", "1")  # Tennis 1/PB 1
        page.select_option("#Start_Time", "41")  # 8:00 PM
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

            write_github_summary(
                f"### ❌ Court Booking Failed\n"
                f"* **Target Date:** {target_date}\n"
                f"* **Time:** 8:00 PM (Court 1)\n"
                f"* **Reason:** Time slot was unavailable, already reserved, or returned an error."
            )

            browser.close()
            # Force GitHub Actions to fail (Red ❌)
            sys.exit(1)

        else:
            print("✅ Reservation completed successfully!")
            write_github_summary(
                f"### ✅ Court Booking Successful!\n"
                f"* **Target Date:** {target_date}\n"
                f"* **Time:** 8:00 PM (Court 1)\n"
                f"* **Type:** Pickleball"
            )

        browser.close()


if __name__ == "__main__":
    run()
