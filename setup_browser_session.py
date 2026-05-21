"""setup_browser_session.py — one-time browser login setup for all services."""

from playwright.sync_api import sync_playwright
import json
import os
import time

SESSION_FILE = os.path.expanduser("~/.config/autonomous_agent_session.json")


def setup_session():
    """Open browser, let user log in to all services, save session."""
    print("=" * 60)
    print("BROWSER SESSION SETUP")
    print("=" * 60)
    print("This browser will open. Please log in to:")
    print("  1. Microsoft Teams / Outlook (teams.microsoft.com)")
    print("  2. Google Calendar (calendar.google.com)")
    print("  3. LinkedIn (linkedin.com)")
    print("  4. Any other services you want the agent to use")
    print()
    print("When done logging in to all services, press ENTER here.")
    print("=" * 60)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # Open all services in separate tabs so user can log into all at once
        services = [
            ("LinkedIn",       "https://www.linkedin.com/login"),
            ("Microsoft Teams","https://teams.microsoft.com"),
            ("Outlook",        "https://outlook.cloud.microsoft"),
            ("Google Calendar","https://calendar.google.com"),
        ]
        for name, url in services:
            page = context.new_page()
            try:
                page.goto(url, timeout=20000, wait_until="domcontentloaded")
                print("Opened: " + name)
            except Exception:
                print("Could not open: " + name)

        input("\nPress ENTER after logging in to all services...")

        # Save session cookies and storage
        storage = context.storage_state()
        with open(SESSION_FILE, "w") as f:
            json.dump(storage, f)

        print(f"\nSession saved to: {SESSION_FILE}")
        print("The agent will now use this session automatically.")
        browser.close()


if __name__ == "__main__":
    setup_session()
