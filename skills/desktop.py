"""skills/desktop.py — desktop UI interaction via pyautogui."""

import tempfile
import subprocess
import time
from pathlib import Path

import pyautogui
import pyperclip
from langchain_core.tools import tool

from config.platform_utils import take_screenshot as _take_ss

_DEFAULT_SCREENSHOT = str(Path(tempfile.gettempdir()) / "screenshot.png")


@tool
def take_screenshot(save_path: str = "") -> str:
    """
    Capture the current desktop screenshot and save it to a file.
    Uses scrot if available, falls back to Playwright browser screenshot.

    Args:
        save_path: Absolute path to save the PNG screenshot. Auto-set if empty.

    Returns:
        str: Path to the saved screenshot file.
    """
    if not save_path:
        save_path = _DEFAULT_SCREENSHOT
    if _take_ss(save_path):
        return f"Screenshot saved: {save_path}"
    try:
        from skills.browser import _get_page
        page = _get_page()
        page.screenshot(path=save_path)
        return f"Browser screenshot saved: {save_path}"
    except Exception as e:
        return f"Screenshot failed: {e}"


@tool
def click_on_screen(x: int, y: int) -> str:
    """
    Click at absolute screen pixel coordinates.

    Args:
        x: Horizontal pixel coordinate.
        y: Vertical pixel coordinate.

    Returns:
        str: Confirmation message.
    """
    pyautogui.click(x, y)
    time.sleep(0.3)
    return f"Clicked at ({x}, {y})"


@tool
def double_click_on_screen(x: int, y: int) -> str:
    """
    Double-click at absolute screen pixel coordinates.

    Args:
        x: Horizontal pixel coordinate.
        y: Vertical pixel coordinate.

    Returns:
        str: Confirmation message.
    """
    pyautogui.doubleClick(x, y)
    time.sleep(0.3)
    return f"Double-clicked at ({x}, {y})"


@tool
def type_text(text: str) -> str:
    """
    Type text at the current cursor position using clipboard paste.
    Supports Unicode, special characters, and long text.

    Args:
        text: Text string to type. Supports any characters.

    Returns:
        str: Confirmation message.
    """
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.3)
    return f"Typed text ({len(text)} chars)"


@tool
def press_key(key: str) -> str:
    """
    Press a single keyboard key or hotkey combination.

    Args:
        key: Key name or hotkey string.
             Single keys: 'enter', 'tab', 'escape', 'backspace', 'delete'
             Hotkeys: 'ctrl+c', 'ctrl+v', 'ctrl+s', 'alt+f4', 'ctrl+a'

    Returns:
        str: Confirmation message.
    """
    if "+" in key:
        parts = key.split("+")
        pyautogui.hotkey(*parts)
    else:
        pyautogui.press(key)
    time.sleep(0.2)
    return f"Pressed: {key}"


@tool
def find_and_click_image(template_path: str, confidence: float = 0.8) -> str:
    """
    Find a UI element on screen by image template matching and click it.
    Use this to click buttons, icons, or UI elements you have a screenshot of.

    Args:
        template_path: Absolute path to the template image (PNG/JPG).
        confidence: Match confidence threshold 0.0–1.0. Default 0.8.

    Returns:
        str: Confirmation with coordinates, or error if not found.
    """
    try:
        location = pyautogui.locateCenterOnScreen(template_path, confidence=confidence)
        if location:
            pyautogui.click(location)
            time.sleep(0.3)
            return f"Found and clicked element at {location}"
        return f"Element not found on screen (template: {template_path})"
    except Exception as e:
        return f"Error finding element: {e}"


@tool
def open_application(app_name: str) -> str:
    """
    Launch a desktop application by its command name.
    After launching, use take_screenshot to see the current state.

    Args:
        app_name: Application command name (e.g. 'firefox', 'code', 'nautilus').

    Returns:
        str: Confirmation or error message.
    """
    try:
        subprocess.Popen([app_name], start_new_session=True)
        time.sleep(2)
        return f"Launched: {app_name}. Use take_screenshot to see current state."
    except FileNotFoundError:
        return f"Application not found: {app_name}"


@tool
def scroll(direction: str, amount: int = 3) -> str:
    """
    Scroll the screen up or down at the current mouse position.

    Args:
        direction: 'up' or 'down'.
        amount: Number of scroll clicks. Default 3.

    Returns:
        str: Confirmation message.
    """
    clicks = amount if direction == "up" else -amount
    pyautogui.scroll(clicks)
    time.sleep(0.2)
    return f"Scrolled {direction} by {amount}"
