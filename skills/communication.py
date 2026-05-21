"""skills/communication.py — email, Teams, LinkedIn, camera, and web search tools."""

import base64
import shutil
import subprocess
import time
import urllib.parse
from pathlib import Path

import httpx
from langchain_core.tools import tool

from config.platform_utils import (
    copy_to_clipboard, get_ffmpeg_camera_args, get_os, get_pictures, get_videos, open_file,
)
from config.settings import settings


def _wait_login(page, service: str, timeout: int = 120) -> bool:
    """
    Return True immediately if already logged in, otherwise wait for login.

    Args:
        page: Playwright page object.
        service: Service name shown in the action prompt.
        timeout: Maximum seconds to wait for login.

    Returns:
        bool: True if logged in, False if timed out.
    """
    indicators = ["login", "signin", "microsoftonline", "oauth", "accounts.google"]
    if not any(x in page.url.lower() for x in indicators):
        return True
    print(f"\n[ACTION REQUIRED] Please log in to {service} in the browser.")
    print(f"Waiting up to {timeout} seconds...\n")
    start = time.time()
    while time.time() - start < timeout:
        if not any(x in page.url.lower() for x in indicators):
            print("[LOGIN DETECTED] Continuing...\n")
            return True
        time.sleep(2)
    return False


def _fresh_page():
    """
    Return a fresh Playwright page by closing any existing session first.

    Returns:
        Page: New Playwright page object.
    """
    from skills.browser import _get_page, close_browser
    close_browser()
    return _get_page()


@tool
def cancel_teams_meeting(meeting_title: str, notify_attendees: bool = True, message: str = "") -> str:
    """
    Cancel a Teams/Outlook meeting by its title and notify attendees.

    Finds the meeting in Outlook calendar by title, cancels it,
    and sends a cancellation email to all attendees with the given message.

    Args:
        meeting_title: Title of the meeting to cancel (e.g. 'Testing').
        notify_attendees: Whether to send cancellation email. Default True.
        message: Cancellation message to include in the notification.

    Returns:
        str: Status message describing what was done.
    """
    page = _fresh_page()
    try:
        page.goto("https://outlook.cloud.microsoft/calendar", timeout=30000)
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        time.sleep(5)

        if not _wait_login(page, "Microsoft"):
            return "Login required. Run: python setup_browser_session.py"

        try:
            page.click(f"[aria-label*='{meeting_title}']", timeout=8000)
            time.sleep(2)
        except Exception:
            try:
                page.click(f"text={meeting_title}", timeout=5000)
                time.sleep(2)
            except Exception:
                return f"Meeting '{meeting_title}' not found in calendar."

        cancelled = False
        for selector in [
            "button:has-text('Cancel')",
            "[aria-label='Cancel event']",
            "button:has-text('Cancel event')",
            "[aria-label='Delete']",
        ]:
            try:
                page.click(selector, timeout=4000)
                time.sleep(1)
                cancelled = True
                break
            except Exception:
                continue

        if not cancelled:
            return f"Could not find cancel button for '{meeting_title}'."

        if notify_attendees:
            try:
                if message:
                    try:
                        page.fill(
                            "[aria-label='Message body'], textarea, [role='textbox']",
                            message,
                            timeout=3000,
                        )
                    except Exception:
                        pass
                page.click(
                    "button:has-text('Send cancellation'), button:has-text('Send')",
                    timeout=5000,
                )
                time.sleep(2)
                return (
                    f"Meeting '{meeting_title}' cancelled.\n"
                    f"Cancellation notification sent to all attendees."
                    + (f"\nMessage: {message}" if message else "")
                )
            except Exception as e:
                return (
                    f"Meeting '{meeting_title}' cancelled but notification failed: {e}\n"
                    "Please send the cancellation manually from Outlook."
                )

        return f"Meeting '{meeting_title}' cancelled."

    except Exception as e:
        return f"Error cancelling meeting: {e}"


@tool
def send_teams_message(recipient: str, message: str) -> str:
    """
    Send a chat message to a person on Microsoft Teams by their name.
    Use this for Teams chat messages — NOT for email.

    Args:
        recipient: Full name of the person in Teams (e.g. 'Tamanna Thakur').
        message: Message text to send.

    Returns:
        str: Status message.
    """
    page = _fresh_page()
    try:
        page.set_viewport_size({"width": 1280, "height": 950})
        page.goto("https://teams.microsoft.com/v2/", timeout=30000)
        page.wait_for_load_state("domcontentloaded", timeout=15000)

        try:
            page.wait_for_selector("[aria-label='Chat (Ctrl+Shift+2)']", timeout=20000)
        except Exception:
            pass
        try:
            page.wait_for_selector("#loading-screen", state="hidden", timeout=15000)
        except Exception:
            pass
        time.sleep(2)

        if not _wait_login(page, "Teams"):
            return "Login required. Run: python setup_browser_session.py"

        page.click("button[aria-label='Chat (Ctrl+Shift+2)']", timeout=8000)
        time.sleep(2)

        try:
            page.fill(
                "input[aria-label*='chat or channel' i], "
                "input[aria-label*='Search' i], "
                "input[aria-label='Press Ctrl+Alt+G to go right to a chat or channel']",
                recipient,
            )
        except Exception:
            page.keyboard.press("Control+Alt+G")
            time.sleep(0.5)
            page.keyboard.type(recipient)
        time.sleep(3)

        try:
            page.click(f"[role='option'][aria-label*='{recipient.split()[0]}']", timeout=8000)
            time.sleep(2)
        except Exception:
            try:
                page.click(f"[role='option']", timeout=5000)
                time.sleep(2)
            except Exception:
                page.keyboard.press("ArrowDown")
                page.keyboard.press("Enter")
                time.sleep(2)

        page.click(
            "[aria-label='Type a message'], div[contenteditable='true'][role='textbox']",
            timeout=8000,
        )
        time.sleep(0.3)
        page.keyboard.type(message)
        time.sleep(0.3)
        page.keyboard.press("Enter")
        time.sleep(1)
        return f"Message sent to {recipient} on Teams."

    except Exception as e:
        return f"Teams message error: {e}"


@tool
def send_gmail(to: str, subject: str, body: str) -> str:
    """
    Send an email via Gmail.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Email body text.

    Returns:
        str: Status message.
    """
    from skills.browser import _get_page
    page = _get_page()
    try:
        page.goto("https://mail.google.com/mail/u/0/#compose", timeout=30000)
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        time.sleep(5)

        if not _wait_login(page, "Gmail"):
            return "Login required. Run: python setup_browser_session.py"
        time.sleep(2)

        try:
            page.fill("[name='to'], [aria-label='To']", to)
            page.keyboard.press("Tab")
            time.sleep(0.3)
        except Exception:
            pass

        try:
            page.fill("[name='subjectbox'], [aria-label='Subject']", subject)
            time.sleep(0.3)
        except Exception:
            pass

        try:
            page.click("[aria-label='Message Body'], [role='textbox']", timeout=5000)
            time.sleep(0.3)
            page.keyboard.type(body)
            time.sleep(0.3)
        except Exception:
            pass

        try:
            page.click("[aria-label='Send (Ctrl-Enter)']", timeout=5000)
        except Exception:
            page.keyboard.press("Control+Enter")
        time.sleep(2)
        return f"Email sent to {to} | Subject: {subject}"

    except Exception as e:
        return f"Gmail error: {e}"


def _fill_recipient(page, field_label: str, name: str) -> None:
    """
    Type a recipient name into a To/CC field and select the autocomplete suggestion.

    Args:
        page: Playwright page object.
        field_label: Aria-label of the field, e.g. 'To' or 'Cc'.
        name: Full name to type for autocomplete.
    """
    try:
        page.click(
            f"[aria-label='{field_label}'], "
            f"div[aria-label='{field_label}'] div[role='textbox']",
            timeout=8000,
        )
        time.sleep(0.4)
        page.keyboard.type(name)
        time.sleep(3)
        option = page.query_selector(
            ".ms-PeoplePicker-result [role='option'], "
            "div[role='listbox'] [role='option'], "
            "[role='option']"
        )
        if option:
            option.click()
        else:
            page.keyboard.press("Enter")
        time.sleep(0.5)
    except Exception:
        pass


@tool
def send_outlook_email(to: str, subject: str, body: str, cc: str = "") -> str:
    """
    Compose an email via Outlook web.
    Fills all fields (To, CC, Subject, Body) and leaves browser open for review.
    User reviews and clicks Send to confirm.

    Args:
        to: Recipient name e.g. 'Tamanna Thakur'. Outlook resolves from contacts.
        subject: Email subject line.
        body: Full email body text (not a file path).
        cc: CC recipient name e.g. 'Ishmeet Kaur' (optional).

    Returns:
        str: Status message confirming fields were filled.
    """
    _b = body.strip()
    if _b.startswith("/") and Path(_b).exists():
        body = Path(_b).read_text(encoding="utf-8")

    page = _fresh_page()
    try:
        page.goto("https://outlook.cloud.microsoft/mail/deeplink/compose", timeout=30000)
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        time.sleep(5)

        login_indicators = ["login", "signin", "microsoftonline", "oauth"]
        if any(x in page.url.lower() for x in login_indicators):
            print("\n[ACTION REQUIRED] Please log in to Outlook in the browser.")
            start = time.time()
            while time.time() - start < 120:
                if not any(x in page.url.lower() for x in login_indicators):
                    break
                time.sleep(2)
        time.sleep(2)

        _fill_recipient(page, "To", to)

        if cc:
            _fill_recipient(page, "Cc", cc)

        try:
            page.click("input[aria-label='Subject'], [aria-label='Subject']", timeout=5000)
            time.sleep(0.3)
            page.keyboard.type(subject)
            time.sleep(0.3)
        except Exception:
            pass

        try:
            copy_to_clipboard(body)
            body_clicked = False
            for sel in [
                "div[aria-label='Message body, ']",
                "div[aria-label='Message body']",
                "[role='textbox'][aria-label*='Message body']",
                "div[contenteditable='true'][aria-label*='body']",
                "div[contenteditable='true']",
            ]:
                try:
                    page.click(sel, timeout=3000)
                    body_clicked = True
                    break
                except Exception:
                    continue
            if body_clicked:
                time.sleep(0.4)
                page.keyboard.press("Control+a")
                time.sleep(0.2)
                page.keyboard.press("Control+v")
                time.sleep(1)
        except Exception:
            pass

        print("\n[REVIEW] Email composed in browser. Please review and click Send.")
        return (
            f"Email composed in Outlook browser.\n"
            f"To: {to}" + (f" | CC: {cc}" if cc else "") + "\n"
            f"Subject: {subject}\n"
            "Please review and click Send to confirm."
        )

    except Exception as e:
        return f"Outlook email error: {e}"


@tool
def linkedin_send_connection_request(profile_url: str, note: str = "") -> str:
    """
    Send a LinkedIn connection request to a person.
    By default sends WITHOUT a note. Only includes note if explicitly provided.
    Note must be under 200 characters.

    Args:
        profile_url: Full LinkedIn profile URL, or search URL with name+company keywords.
        note: Optional polite note under 200 chars. Leave empty to send without note.

    Returns:
        str: Status message.
    """
    from skills.browser import _get_page, close_browser

    if note and len(note) > 200:
        note = note[:197] + "..."

    close_browser()
    page = _get_page()
    try:
        page.goto(profile_url, timeout=30000)
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        time.sleep(4)

        if not _wait_login(page, "LinkedIn"):
            return "Login required. Run: python setup_browser_session.py"
        time.sleep(2)

        if "login" in page.url.lower() or "signin" in page.url.lower():
            return "LinkedIn session expired. Run: python setup_browser_session.py"

        if "search/results" in page.url:
            try:
                page.wait_for_selector("a[href*='/in/']", timeout=10000)
            except Exception:
                pass
            time.sleep(2)
            clicked_profile = False
            for link in page.query_selector_all("a[href*='/in/']"):
                try:
                    href = link.get_attribute("href") or ""
                    if "/in/" in href and "search" not in href and "miniProfile" not in href:
                        link.click()
                        page.wait_for_load_state("domcontentloaded", timeout=15000)
                        time.sleep(4)
                        clicked_profile = True
                        break
                except Exception:
                    continue
            if not clicked_profile:
                return "Could not find person in LinkedIn search results. Please provide a direct profile URL."

        for wait_sel in [
            "button:has-text('Connect')",
            "button:has-text('Message')",
            "button:has-text('Follow')",
        ]:
            try:
                page.wait_for_selector(wait_sel, timeout=8000)
                break
            except Exception:
                continue
        time.sleep(2)

        profile_name = ""
        try:
            title = page.title()
            if " | " in title:
                profile_name = title.split(" | ")[0].strip()
        except Exception:
            pass

        connect_clicked = False
        first_name = profile_name.split()[0] if profile_name else ""

        if first_name:
            try:
                el = page.query_selector(
                    "a[aria-label*='Invite'][aria-label*='" + first_name + "'][aria-label*='connect' i], "
                    "button[aria-label*='Invite'][aria-label*='" + first_name + "'][aria-label*='connect' i]"
                )
                if el and el.is_visible():
                    el.evaluate("e => e.click()")
                    connect_clicked = True
                    time.sleep(2)
            except Exception:
                pass

        if not connect_clicked:
            try:
                more_btns = []
                for b in page.query_selector_all("button"):
                    try:
                        if not b.is_visible():
                            continue
                        txt = b.inner_text().strip().replace("\n", " ")
                        aria = b.get_attribute("aria-label") or ""
                        bb = b.bounding_box()
                        if bb and txt == "More" and aria == "" and 200 < bb["y"] < 800:
                            more_btns.append((bb["y"], b))
                    except Exception:
                        continue
                if more_btns:
                    more_btns.sort(key=lambda x: x[0], reverse=True)
                    more_btns[0][1].evaluate("e => e.click()")
                    time.sleep(1.5)
                    for item in page.query_selector_all("li, div.artdeco-dropdown__item, [role='menuitem']"):
                        try:
                            if item.is_visible() and "Connect" in item.inner_text():
                                item.evaluate("e => e.click()")
                                connect_clicked = True
                                time.sleep(2)
                                break
                        except Exception:
                            continue
                    if not connect_clicked:
                        page.keyboard.press("Escape")
            except Exception:
                pass

        if not connect_clicked:
            follow_label = "Follow " + profile_name if profile_name else ""
            follow_el = page.query_selector(
                "a[aria-label='" + follow_label + "'], button[aria-label='" + follow_label + "']"
            )
            if follow_el and follow_el.is_visible():
                return (
                    "Cannot send connection request to " + (profile_name or "this person") + ". "
                    "Their profile only shows Follow — already connected, request pending, or creator mode."
                )
            return "Connect button not found. May already be connected or pending."

        if note:
            try:
                page.click("button:has-text('Add a note')", timeout=4000)
                time.sleep(0.5)
                page.fill("textarea[name='message']", note)
                time.sleep(0.3)
            except Exception:
                pass
        else:
            try:
                page.click("button:has-text('Send without a note')", timeout=3000)
                time.sleep(1)
                return f"Connection request sent (without note) to {page.url}"
            except Exception:
                pass

        for selector in [
            "button:has-text('Send now')",
            "button:has-text('Send')",
            "[aria-label*='Send' i]",
        ]:
            try:
                page.click(selector, timeout=4000)
                time.sleep(1)
                return f"Connection request sent to {page.url}"
            except Exception:
                continue

        return f"Connection request sent (or already pending) for {page.url}"

    except Exception as e:
        return f"LinkedIn error: {e}"


@tool
def linkedin_send_message(profile_url: str, message: str) -> str:
    """
    Send a message to a LinkedIn connection.

    Args:
        profile_url: Full LinkedIn profile URL of the person to message.
        message: Message text to send.

    Returns:
        str: Status message.
    """
    from skills.browser import _get_page, close_browser
    close_browser()
    page = _get_page()
    try:
        page.goto(profile_url, timeout=30000)
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        time.sleep(4)

        if not _wait_login(page, "LinkedIn"):
            return "Login required. Run: python setup_browser_session.py"
        time.sleep(2)

        if "login" in page.url.lower() or "signin" in page.url.lower():
            return "LinkedIn session expired. Run: python setup_browser_session.py"

        if "search/results" in page.url:
            try:
                page.wait_for_selector("a[href*='/in/']", timeout=10000)
            except Exception:
                pass
            time.sleep(2)
            for link in page.query_selector_all("a[href*='/in/']"):
                href = link.get_attribute("href") or ""
                if "/in/" in href and "search" not in href and "miniProfile" not in href:
                    link.click()
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                    time.sleep(4)
                    break

        for ws in ["button:has-text('Message')", "a[aria-label*='Message' i]"]:
            try:
                page.wait_for_selector(ws, timeout=8000)
                break
            except Exception:
                continue
        time.sleep(2)

        msg_clicked = False
        for sel in [
            "a[aria-label*='Message' i]",
            "button:has-text('Message')",
        ]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.evaluate("e => e.click()")
                    msg_clicked = True
                    time.sleep(2)
                    break
            except Exception:
                continue

        if not msg_clicked:
            return "Message button not found. You may not be connected with this person."

        try:
            page.click("[aria-label*='message' i], [placeholder*='message' i], div[contenteditable='true']", timeout=5000)
            time.sleep(0.3)
            page.keyboard.type(message)
            time.sleep(0.3)
            page.keyboard.press("Enter")
            time.sleep(1)
            return "Message sent via LinkedIn."
        except Exception as e:
            return f"Could not send message: {e}"

    except Exception as e:
        return f"LinkedIn message error: {e}"


@tool
def search_web(query: str) -> str:
    """
    Search the web using Google and return top results text.

    Args:
        query: Search query string.

    Returns:
        str: Top search results text (first 3000 characters).
    """
    from skills.browser import _get_page
    page = _get_page()
    try:
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        page.goto(url, timeout=30000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        time.sleep(2)
        return page.inner_text("body")[:3000]
    except Exception as e:
        return f"Search error: {e}"


@tool
def open_camera_and_capture(save_path: str = "") -> str:
    """
    Capture a photo from the webcam and save it.
    Uses fswebcam on Linux, imagesnap on Mac, or ffmpeg on Windows.
    Opens the photo automatically after capture.

    Args:
        save_path: Absolute path to save the photo. Auto-set if empty.

    Returns:
        str: Status message with saved file path.
    """
    if not save_path:
        save_path = str(get_pictures() / "capture.jpg")

    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    os_name = get_os()

    if os_name == "linux" and shutil.which("fswebcam"):
        result = subprocess.run(
            ["fswebcam", "-r", "1280x720", "--no-banner", "-S", "30", save_path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            open_file(save_path)
            return f"Photo captured and saved: {save_path}"

    if os_name == "mac" and shutil.which("imagesnap"):
        result = subprocess.run(
            ["imagesnap", "-w", "1", save_path],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            open_file(save_path)
            return f"Photo captured and saved: {save_path}"

    if shutil.which("ffmpeg"):
        result = subprocess.run(
            ["ffmpeg", "-y", *get_ffmpeg_camera_args(), "-frames:v", "1", save_path],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            open_file(save_path)
            return f"Photo captured and saved: {save_path}"

    return (
        "No camera tool found. "
        "Linux: sudo apt install fswebcam | "
        "Mac: brew install imagesnap | "
        "All: sudo apt install ffmpeg"
    )


@tool
def record_video(save_path: str = "", duration: int = 30) -> str:
    """
    Record a video from the webcam for the specified duration.
    Uses ffmpeg which works on Linux, Windows, and macOS.
    Opens the video automatically after recording.

    Args:
        save_path: Absolute path to save the video (.mp4). Auto-set if empty.
        duration: Recording duration in seconds. Default 30.

    Returns:
        str: Status message with saved file path.
    """
    if not save_path:
        save_path = str(get_videos() / "recording.mp4")

    Path(save_path).parent.mkdir(parents=True, exist_ok=True)

    if not shutil.which("ffmpeg"):
        subprocess.run(["sudo", "apt", "install", "-y", "ffmpeg"], timeout=120)
        if not shutil.which("ffmpeg"):
            return "ffmpeg not installed. Run: sudo apt install ffmpeg"

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            *get_ffmpeg_camera_args(),
            "-f", "alsa", "-i", "default",
            "-t", str(duration),
            "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
            save_path,
        ],
        capture_output=True, text=True, timeout=duration + 30,
    )

    if result.returncode == 0 and Path(save_path).exists():
        open_file(save_path)
        return f"Video recorded ({duration}s) and saved: {save_path}"

    result2 = subprocess.run(
        [
            "ffmpeg", "-y",
            *get_ffmpeg_camera_args(),
            "-t", str(duration),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            save_path,
        ],
        capture_output=True, text=True, timeout=duration + 30,
    )

    if result2.returncode == 0 and Path(save_path).exists():
        open_file(save_path)
        return f"Video recorded ({duration}s, no audio) and saved: {save_path}"

    return f"Video recording failed: {result2.stderr[-200:]}"


@tool
def send_teams_file(recipient: str, file_path: str, message: str = "") -> str:
    """
    Send a file to a person on Microsoft Teams via chat.
    Uses the Attach file option in the message toolbar.

    Args:
        recipient: Full name of the person in Teams (e.g. 'Tamanna Thakur').
        file_path: Absolute path to the file to send.
        message: Optional message to include with the file.

    Returns:
        str: Status message.
    """
    if not Path(file_path).exists():
        return f"File not found: {file_path}"

    page = _fresh_page()
    try:
        page.set_viewport_size({"width": 1280, "height": 950})
        page.goto("https://teams.microsoft.com/v2/", timeout=30000)
        page.wait_for_load_state("domcontentloaded", timeout=15000)

        try:
            page.wait_for_selector("[aria-label='Chat (Ctrl+Shift+2)']", timeout=20000)
        except Exception:
            pass
        try:
            page.wait_for_selector("#loading-screen", state="hidden", timeout=15000)
        except Exception:
            pass
        time.sleep(2)

        if not _wait_login(page, "Teams"):
            return "Login required. Run: python setup_browser_session.py"

        page.click("button[aria-label='Chat (Ctrl+Shift+2)']", timeout=8000)
        time.sleep(2)

        page.keyboard.press("Control+Alt+G")
        time.sleep(0.5)
        page.keyboard.type(recipient)
        time.sleep(3)
        try:
            page.click(f"[role='option'][aria-label*='{recipient.split()[0]}']", timeout=8000)
            time.sleep(2)
        except Exception:
            try:
                page.click(f"[role='option']", timeout=5000)
                time.sleep(2)
            except Exception:
                page.keyboard.press("ArrowDown")
                page.keyboard.press("Enter")
                time.sleep(2)

        page.click(
            "[data-tid='sendMessageCommands-message-extension-flyout-command']",
            timeout=8000,
        )
        time.sleep(2)

        page.click("text=Attach file", timeout=5000)
        time.sleep(2)

        file_input = page.query_selector("input[type='file']")
        if file_input:
            file_input.set_input_files(str(file_path))
            time.sleep(2)
        else:
            page.click("text=Upload from this device", timeout=5000)
            time.sleep(1)
            file_input = page.query_selector("input[type='file']")
            if file_input:
                file_input.set_input_files(str(file_path))
                time.sleep(5)

        if message:
            try:
                page.keyboard.type(message)
                time.sleep(0.3)
            except Exception:
                pass

        page.keyboard.press("Enter")
        time.sleep(2)
        return f"File '{Path(file_path).name}' sent to {recipient} on Teams."

    except Exception as e:
        return f"Teams file send error: {e}"


@tool
def read_image_and_describe(image_path: str) -> str:
    """
    Read a local image file and return a detailed description of its contents.
    Use this when user provides a reference image and asks you to match/replicate it.
    Uses the local vision model (llava) via Ollama — no cloud required.

    Args:
        image_path: Absolute path to the image file (.png, .jpg, .jpeg, .webp).

    Returns:
        str: Detailed description of the image contents, layout, colors, and design.
    """
    path = Path(image_path)
    if not path.exists():
        return f"Image not found: {image_path}"

    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    try:
        payload = {
            "model": settings.vision_model,
            "prompt": (
                "You are a UI developer. Describe this design precisely for HTML/CSS implementation. "
                "Cover ALL of: background color/gradient, button colors per group (numbers/operators/equals/clear), "
                "text colors, layout type (grid columns/rows), font sizes, border-radius, box-shadow, padding, "
                "display area (single or dual, colors, font size), any special button sizing (wide/tall). "
                "List every visible UI element with exact CSS values where possible."
            ),
            "images": [image_b64],
            "stream": False,
        }
        response = httpx.post(
            f"{settings.ollama_base_url}/api/generate",
            json=payload,
            timeout=180,
        )
        response.raise_for_status()
        return response.json().get("response", "Could not describe image.")
    except Exception as e:
        return f"Image description error: {e}"
