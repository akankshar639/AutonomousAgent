"""skills package — pluggable capability modules for the autonomous agent."""
from .filesystem import create_docx
from .browser import (
    open_url, get_page_text, click_element, fill_field,
    browser_press_key, wait_for_element, wait_for_login,
    get_current_url, close_browser_session,
)
from .communication import (
    cancel_teams_meeting, send_teams_message, send_gmail, send_outlook_email,
    linkedin_send_connection_request, linkedin_send_message,
    search_web, open_camera_and_capture, record_video,
    send_teams_file, read_image_and_describe,
)
from .calendar_skill import schedule_teams_meeting, schedule_google_calendar_event
from .desktop import (
    take_screenshot, click_on_screen, double_click_on_screen, type_text,
    press_key, find_and_click_image, open_application, scroll,
)
from .uitars import uitars_act, uitars_screenshot_and_describe
from .media import transcribe_video, extract_document_text

__all__ = [
    "create_docx",
    "open_url", "get_page_text", "click_element", "fill_field",
    "browser_press_key", "wait_for_element", "wait_for_login",
    "get_current_url", "close_browser_session",
    "cancel_teams_meeting", "send_teams_message", "send_gmail", "send_outlook_email",
    "linkedin_send_connection_request", "linkedin_send_message",
    "search_web", "open_camera_and_capture", "record_video",
    "send_teams_file", "read_image_and_describe",
    "schedule_teams_meeting", "schedule_google_calendar_event",
    "take_screenshot", "click_on_screen", "double_click_on_screen", "type_text",
    "press_key", "find_and_click_image", "open_application", "scroll",
    "uitars_act", "uitars_screenshot_and_describe",
    "transcribe_video", "extract_document_text",
]
