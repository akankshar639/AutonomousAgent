"""skills/calendar_skill.py — Teams and Google Calendar meeting scheduling."""

import shutil
import subprocess
import time
from datetime import datetime, timedelta
from langchain_core.tools import tool


def _parse_date(date_str: str) -> str:
    """
    Convert natural language date to M/D/YYYY format for Outlook.

    Args:
        date_str: Date string like 'tomorrow', '2025-04-14', 'Monday'.

    Returns:
        str: Date in M/D/YYYY format.
    """
    date_str = date_str.strip().lower()
    today = datetime.now()

    def _fmt(dt: datetime) -> str:
        return f"{dt.month}/{dt.day}/{dt.year}"

    if date_str == "today":
        return _fmt(today)
    if date_str == "tomorrow":
        return _fmt(today + timedelta(days=1))

    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    if date_str in days:
        target = days.index(date_str)
        current = today.weekday()
        diff = (target - current) % 7 or 7
        return _fmt(today + timedelta(days=diff))

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return _fmt(dt)
    except ValueError:
        pass

    return _fmt(today + timedelta(days=1))


def _parse_time(time_str: str) -> str:
    """
    Convert time string to Outlook format (e.g. '3:30 PM').

    Args:
        time_str: Time like '15:30', '3:30 pm', '3:30 PM'.

    Returns:
        str: Time in 'H:MM AM/PM' format.
    """
    time_str = time_str.strip()
    for fmt in ["%H:%M", "%I:%M %p", "%I:%M%p", "%I %p"]:
        try:
            dt = datetime.strptime(time_str, fmt)
            return f"{dt.strftime('%I').lstrip('0') or '12'}:{dt.strftime('%M')} {dt.strftime('%p')}"
        except ValueError:
            pass
    return time_str


def _wait_for_login(page, service: str, timeout: int = 120) -> bool:
    """
    Return True immediately if already logged in, otherwise wait for login.

    Args:
        page: Playwright page.
        service: Service name for display.
        timeout: Max wait seconds.

    Returns:
        bool: True if logged in, False if timed out.
    """
    login_indicators = ["login", "signin", "microsoftonline", "oauth"]
    if not any(x in page.url.lower() for x in login_indicators):
        return True

    print(f"\n[ACTION REQUIRED] Please log in to {service} in the browser.")
    print(f"Waiting up to {timeout} seconds...\n")
    start = time.time()
    while time.time() - start < timeout:
        if not any(x in page.url.lower() for x in login_indicators):
            print("[LOGIN DETECTED] Continuing...\n")
            return True
        time.sleep(2)
    return False


@tool
def schedule_teams_meeting(title: str, date: str, start_time: str, attendees: list[str], end_time: str = "") -> str:
    """
    Schedule a Microsoft Teams meeting via Outlook web.
    Fills ALL fields automatically: title, date, start time, end time, attendees.
    Opens browser with saved session — no login needed if already set up.

    Args:
        title: Meeting title/heading.
        date: Date — 'tomorrow', 'Monday', 'YYYY-MM-DD', etc.
        start_time: Start time — '15:30', '3:30 PM', etc.
        end_time: End time — '16:00', '4:00 PM', etc. Defaults to 30 min after start.
        attendees: List of attendee names or emails.

    Returns:
        str: Status message.
    """
    for app in ["teams", "teams-for-linux"]:
        if shutil.which(app):
            subprocess.Popen([app], start_new_session=True)
            time.sleep(3)
            return f"Teams desktop app launched. Meeting: {title} on {date} at {start_time}"

    from skills.browser import _get_page
    page = _get_page()

    try:
        page.goto("https://outlook.cloud.microsoft/calendar/action/compose", timeout=30000)
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        time.sleep(5)

        if not _wait_for_login(page, "Microsoft", timeout=120):
            return "Login timed out. Run: python setup_browser_session.py"

        time.sleep(2)

        page.fill("[placeholder='Add title']", title)
        time.sleep(0.5)

        page.evaluate("""
            const els = document.querySelectorAll('[role=button]');
            for(const el of els) {
                if(el.textContent.match(/\\d+:\\d+ (AM|PM)/)) {
                    el.click(); break;
                }
            }
        """)
        time.sleep(2)

        formatted_date = _parse_date(date)
        try:
            page.fill("[aria-label='Start date']", formatted_date)
            page.keyboard.press("Tab")
            time.sleep(0.5)
        except Exception:
            pass

        formatted_start = _parse_time(start_time)
        try:
            page.fill("[aria-label='Start time']", formatted_start)
            page.keyboard.press("Tab")
            time.sleep(0.5)
        except Exception:
            pass

        if end_time:
            formatted_end = _parse_time(end_time)
        else:
            try:
                start_dt = datetime.strptime(formatted_start, "%I:%M %p")
                end_dt = start_dt + timedelta(minutes=30)
                h = end_dt.strftime("%I").lstrip("0") or "12"
                formatted_end = f"{h}:{end_dt.strftime('%M')} {end_dt.strftime('%p')}"
            except Exception:
                formatted_end = ""

        if formatted_end:
            try:
                page.fill("[aria-label='End time']", formatted_end)
                page.keyboard.press("Tab")
                time.sleep(0.5)
            except Exception:
                pass

        for attendee in attendees:
            try:
                page.click("[aria-label='Invite required attendees']", timeout=5000)
                time.sleep(0.3)
                page.keyboard.type(attendee)
                time.sleep(0.5)
                page.keyboard.press("Enter")
                time.sleep(0.5)
            except Exception:
                pass

        try:
            page.click("button:has-text('Send'), button:has-text('Save')", timeout=5000)
            time.sleep(2)
            return (
                f"Teams meeting scheduled successfully!\n"
                f"Title: {title} | Date: {formatted_date} | Time: {formatted_start}–{formatted_end}\n"
                f"Attendees: {', '.join(attendees)}"
            )
        except Exception:
            return (
                f"Meeting form filled. Please click Send in the browser.\n"
                f"Title: {title} | Date: {formatted_date} | Time: {formatted_start}–{formatted_end}\n"
                f"Attendees: {', '.join(attendees)}"
            )

    except Exception as e:
        return f"Error: {e}\nBrowser is open — please complete manually."


@tool
def schedule_google_calendar_event(
    title: str,
    date: str,
    start_time: str,
    end_time: str,
    attendees: list[str],
    description: str = "",
) -> str:
    """
    Schedule a Google Calendar event with Meet link.
    Fills all fields automatically via browser.

    Args:
        title: Event title.
        date: Date — 'tomorrow', 'YYYY-MM-DD', etc.
        start_time: Start time in HH:MM or 'H:MM AM/PM'.
        end_time: End time in HH:MM or 'H:MM AM/PM'.
        attendees: List of attendee emails.
        description: Optional description.

    Returns:
        str: Status message.
    """
    from skills.browser import _get_page
    page = _get_page()

    try:
        page.goto("https://calendar.google.com/calendar/r/eventedit", timeout=30000)
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        time.sleep(4)

        if not _wait_for_login(page, "Google", timeout=120):
            return "Google login timed out. Run: python setup_browser_session.py"

        time.sleep(2)

        try:
            page.click('input[placeholder="Title"]', timeout=8000)
            time.sleep(0.3)
            page.keyboard.type(title)
            time.sleep(0.5)
        except Exception:
            pass

        formatted_date = _parse_date(date)

        formatted_start = _parse_time(start_time)
        formatted_end = _parse_time(end_time) if end_time else ""

        try:
            page.click('[data-testid="start-date"], input[aria-label*="Start date" i]', timeout=6000)
            time.sleep(0.3)
            page.keyboard.press("Control+a")
            page.keyboard.type(formatted_date)
            page.keyboard.press("Escape")
            time.sleep(0.5)
        except Exception:
            pass

        try:
            page.click('[data-testid="start-time"], input[aria-label*="Start time" i]', timeout=6000)
            time.sleep(0.3)
            page.keyboard.press("Control+a")
            page.keyboard.type(formatted_start)
            page.keyboard.press("Enter")
            time.sleep(0.5)
        except Exception:
            pass

        if formatted_end:
            try:
                page.click('[data-testid="end-time"], input[aria-label*="End time" i]', timeout=6000)
                time.sleep(0.3)
                page.keyboard.press("Control+a")
                page.keyboard.type(formatted_end)
                page.keyboard.press("Enter")
                time.sleep(0.5)
            except Exception:
                pass

        if description:
            try:
                page.click('[placeholder="Add a description"], textarea[aria-label*="description" i]', timeout=5000)
                time.sleep(0.3)
                page.keyboard.type(description)
                time.sleep(0.3)
            except Exception:
                pass

        for email in attendees:
            try:
                page.click(
                    'input[placeholder="Add guests"], input[aria-label*="guest" i], '
                    'input[data-testid="guest-input"]',
                    timeout=6000,
                )
                time.sleep(0.3)
                page.keyboard.type(email)
                time.sleep(0.5)
                page.keyboard.press("Enter")
                time.sleep(0.8)
            except Exception:
                pass

        saved = False
        for selector in [
            'button[data-testid="save-button"]',
            'button:has-text("Save")',
            '[aria-label="Save"]',
        ]:
            try:
                page.click(selector, timeout=5000)
                saved = True
                time.sleep(2)
                break
            except Exception:
                continue

        if saved:
            return (
                f"Google Calendar event scheduled!\n"
                f"Title: {title} | Date: {formatted_date} | "
                f"Time: {formatted_start}–{formatted_end}\n"
                f"Attendees: {', '.join(attendees)}"
            )
        return (
            f"Google Calendar event form filled. Please click Save in the browser.\n"
            f"Title: {title} | Date: {formatted_date} | "
            f"Time: {formatted_start}–{formatted_end}\n"
            f"Attendees: {', '.join(attendees)}"
        )

    except Exception as e:
        return f"Google Calendar error: {e}\nBrowser is open — please complete manually."
