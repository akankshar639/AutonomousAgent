"""skills/uitars.py — vision-based desktop interaction using a local vision model."""

import base64
import re
import tempfile
import time
from pathlib import Path

import httpx
import pyautogui
from langchain_core.tools import tool

from config.settings import settings

_SCREENSHOT_PATH = str(Path(tempfile.gettempdir()) / "uitars_screenshot.png")


def _take_screenshot() -> str:
    """
    Capture the current desktop screenshot and return its base64 encoding.

    Returns:
        str: Base64-encoded PNG screenshot.
    """
    screenshot = pyautogui.screenshot()
    screenshot.save(_SCREENSHOT_PATH)
    with open(_SCREENSHOT_PATH, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _ask_vision_model(image_b64: str, instruction: str) -> str:
    """
    Send a screenshot to the local vision model with an instruction.

    Args:
        image_b64: Base64-encoded screenshot PNG.
        instruction: Natural language instruction about what to do on screen.

    Returns:
        str: Vision model response describing the action to take.
    """
    payload = {
        "model": settings.vision_model,
        "prompt": (
            f"You are a desktop UI assistant. Look at this screenshot and answer: {instruction}\n"
            "Be specific: if clicking, give exact pixel coordinates (x, y). "
            "If typing, give the exact text. Keep response short and actionable."
        ),
        "images": [image_b64],
        "stream": False,
    }
    response = httpx.post(
        f"{settings.ollama_base_url}/api/generate",
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return response.json().get("response", "")


@tool
def uitars_act(instruction: str) -> str:
    """
    Use the UI-TARS vision model to understand the current screen and perform an action.

    Takes a screenshot, sends it to a local vision model (llava) with your instruction,
    and executes the suggested action (click, type, scroll, etc.).

    Use this for complex UI interactions where you don't know exact coordinates
    or selectors — the vision model figures it out from the screenshot.

    Args:
        instruction: Natural language description of what to do on screen.
                     Examples:
                     - "Click the Send button"
                     - "Where is the search box? Give me its coordinates."
                     - "What text is in the title bar?"
                     - "Click the Connect button next to John Smith"

    Returns:
        str: Description of what was observed and what action was taken.
    """
    image_b64 = _take_screenshot()
    response = _ask_vision_model(image_b64, instruction)

    # Try to extract and execute click coordinates from the response
    coord_match = re.search(r'\(?\s*(\d{2,4})\s*,\s*(\d{2,4})\s*\)?', response)
    if coord_match and any(kw in instruction.lower() for kw in ["click", "press", "tap", "select"]):
        x, y = int(coord_match.group(1)), int(coord_match.group(2))
        pyautogui.click(x, y)
        time.sleep(0.5)
        return f"Vision model response: {response}\nExecuted: clicked at ({x}, {y})"

    return f"Vision model response: {response}"


@tool
def uitars_screenshot_and_describe() -> str:
    """
    Take a screenshot of the current desktop and return a description of what's visible.
    Use this to understand the current state of the screen before deciding what to do.

    Returns:
        str: Vision model description of the current screen contents.
    """
    image_b64 = _take_screenshot()
    return _ask_vision_model(image_b64, "Describe what you see on this screen in detail.")
