"""skills/browser.py — Playwright browser automation with persistent session."""

import os
import time
from langchain_core.tools import tool

_pw = None
_browser = None
_page = None
_SESSION_FILE = os.path.expanduser("~/.config/autonomous_agent_session.json")


def _get_page():
    """
    Return the current Playwright page, creating a new browser session if needed.
    Uses saved session state if available from setup_browser_session.py.

    Returns:
        Page: Playwright page object ready for interaction.
    """
    global _pw, _browser, _page
    if _page is None or _browser is None:
        from playwright.sync_api import sync_playwright
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx_args = {
            "user_agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "viewport": {"width": 1280, "height": 900},
        }
        if os.path.exists(_SESSION_FILE):
            ctx_args["storage_state"] = _SESSION_FILE
        context = _browser.new_context(**ctx_args)
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        _page = context.new_page()
    return _page


def close_browser() -> None:
    """Close the persistent browser session and reset all state."""
    global _pw, _browser, _page
    if _browser:
        try:
            _browser.close()
        except Exception:
            pass
    if _pw:
        try:
            _pw.stop()
        except Exception:
            pass
    _pw = _browser = _page = None


@tool
def open_url(url: str) -> str:
    """
    Navigate the browser to a URL and return the page title.
    Browser stays open for subsequent tool calls.

    Args:
        url: Full URL to navigate to (e.g. https://linkedin.com).

    Returns:
        str: Page title after navigation.
    """
    page = _get_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(1)
        return f"Navigated to: {url} | Title: {page.title()}"
    except Exception as e:
        return f"Error navigating to {url}: {e}"


@tool
def get_page_text(max_chars: int = 3000) -> str:
    """
    Return the visible text content of the currently open browser page.

    Args:
        max_chars: Maximum characters to return. Default 3000.

    Returns:
        str: Visible text content of the current page.
    """
    page = _get_page()
    try:
        return page.inner_text("body")[:max_chars]
    except Exception as e:
        return f"Error reading page: {e}"


@tool
def click_element(selector: str) -> str:
    """
    Click an element on the current browser page by CSS selector or text.

    Args:
        selector: CSS selector or visible text of the element to click.
                  Examples: 'button[type=submit]', 'text=Connect', '#login-btn'

    Returns:
        str: Confirmation or error message.
    """
    page = _get_page()
    try:
        page.click(selector, timeout=10000)
        time.sleep(0.5)
        return f"Clicked: {selector}"
    except Exception as e:
        return f"Error clicking '{selector}': {e}"


@tool
def fill_field(selector: str, value: str) -> str:
    """
    Fill a text input field on the current browser page.

    Args:
        selector: CSS selector of the input field.
        value: Text value to fill into the field.

    Returns:
        str: Confirmation or error message.
    """
    page = _get_page()
    try:
        page.fill(selector, value)
        return f"Filled '{selector}' with value"
    except Exception as e:
        return f"Error filling field '{selector}': {e}"


@tool
def browser_press_key(key: str) -> str:
    """
    Press a keyboard key inside the browser page.
    Use for Enter, Tab, Escape, ArrowDown etc. while browser is focused.

    Args:
        key: Key name (e.g. 'Enter', 'Tab', 'Escape', 'ArrowDown').

    Returns:
        str: Confirmation message.
    """
    page = _get_page()
    try:
        page.keyboard.press(key)
        time.sleep(0.3)
        return f"Browser pressed key: {key}"
    except Exception as e:
        return f"Error pressing key '{key}': {e}"


@tool
def wait_for_element(selector: str, timeout: int = 10000) -> str:
    """
    Wait for an element to appear on the current browser page.
    Use this after navigation or clicking to wait for the next page to load.

    Args:
        selector: CSS selector to wait for.
        timeout: Maximum wait time in milliseconds. Default 10000.

    Returns:
        str: Confirmation or timeout message.
    """
    page = _get_page()
    try:
        page.wait_for_selector(selector, timeout=timeout)
        return f"Element appeared: {selector}"
    except Exception as e:
        return f"Timeout waiting for '{selector}': {e}"


@tool
def get_current_url() -> str:
    """
    Return the URL of the currently open browser page.

    Returns:
        str: Current page URL.
    """
    page = _get_page()
    return page.url


@tool
def close_browser_session() -> str:
    """
    Close the browser session. Call this when all browser tasks are complete.

    Returns:
        str: Confirmation message.
    """
    close_browser()
    return "Browser session closed."


@tool
def wait_for_login(service: str = "website", timeout_seconds: int = 120) -> str:
    """
    Wait for the user to log in to any website in the current browser session.
    If already logged in (not on a login page), returns immediately.
    Otherwise waits for URL to move away from login page.

    Args:
        service: Name of the service (for display message only).
        timeout_seconds: Max seconds to wait for login. Default 120.

    Returns:
        str: 'logged_in' if detected, 'timeout' if not.
    """
    login_indicators = ["login", "signin", "sign-in", "oauth", "sso", "microsoftonline"]
    page = _get_page()

    if not any(ind in page.url.lower() for ind in login_indicators):
        return "logged_in"

    print(f"\n[ACTION REQUIRED] Please log in to {service} in the browser window.")
    print(f"Waiting up to {timeout_seconds} seconds...\n")

    start = time.time()
    while time.time() - start < timeout_seconds:
        current_url = page.url
        if not any(ind in current_url.lower() for ind in login_indicators):
            print("[LOGIN DETECTED] Login successful. Continuing...\n")
            return "logged_in"
        time.sleep(2)

    print(f"[TIMEOUT] Login not detected after {timeout_seconds}s.")
    return "timeout"
