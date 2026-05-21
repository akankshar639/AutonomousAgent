"""config/platform_utils.py — cross-platform OS detection and utility functions."""

import os
import sys
import shutil
import subprocess
from pathlib import Path


def get_os() -> str:
    """
    Return the current operating system name.

    Returns:
        str: 'linux', 'windows', or 'mac'
    """
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "mac"
    return "linux"


def get_desktop() -> Path:
    """
    Return the Desktop path for the current user on any OS.

    Returns:
        Path: Desktop directory path.
    """
    return Path.home() / "Desktop"


def get_pictures() -> Path:
    """
    Return the Pictures directory for the current user on any OS.

    Returns:
        Path: Pictures directory path.
    """
    return Path.home() / "Pictures"


def get_videos() -> Path:
    """
    Return the Videos directory for the current user on any OS.

    Returns:
        Path: Videos directory path.
    """
    return Path.home() / "Videos"


def get_downloads() -> Path:
    """
    Return the Downloads directory for the current user on any OS.

    Returns:
        Path: Downloads directory path.
    """
    return Path.home() / "Downloads"


def open_file(path: str) -> None:
    """
    Open a file with its default application on any OS.

    Args:
        path: Absolute path to the file.
    """
    os_name = get_os()
    if os_name == "windows":
        os.startfile(path)
    elif os_name == "mac":
        subprocess.Popen(["open", path], start_new_session=True)
    else:
        subprocess.Popen(["xdg-open", path], start_new_session=True)


def copy_to_clipboard(text: str) -> bool:
    """
    Copy text to system clipboard on any OS.

    Args:
        text: Text to copy.

    Returns:
        bool: True if successful.
    """
    os_name = get_os()
    try:
        if os_name == "windows":
            subprocess.run("clip", input=text.encode("utf-16"), check=True)
        elif os_name == "mac":
            subprocess.run("pbcopy", input=text.encode("utf-8"), check=True)
        else:
            # Linux — try xclip, xsel, wl-clipboard in order
            for cmd, args in [
                ("xclip", ["-selection", "clipboard"]),
                ("xsel", ["--clipboard", "--input"]),
                ("wl-copy", []),
            ]:
                if shutil.which(cmd):
                    proc = subprocess.Popen([cmd] + args, stdin=subprocess.PIPE)
                    proc.communicate(input=text.encode("utf-8"))
                    return True
            return False
        return True
    except Exception:
        return False


def take_screenshot(save_path: str) -> bool:
    """
    Take a screenshot on any OS.

    Args:
        save_path: Path to save the screenshot PNG.

    Returns:
        bool: True if successful.
    """
    os_name = get_os()
    try:
        if os_name == "windows":
            import pyautogui
            pyautogui.screenshot().save(save_path)
            return True
        elif os_name == "mac":
            subprocess.run(["screencapture", "-x", save_path], check=True)
            return True
        else:
            # Linux
            if shutil.which("scrot"):
                subprocess.run(["scrot", save_path], check=True, timeout=10)
                return True
            import pyautogui
            pyautogui.screenshot().save(save_path)
            return True
    except Exception:
        return False


def get_camera_device() -> str:
    """
    Return the camera device path for the current OS.

    Returns:
        str: Camera device identifier.
    """
    os_name = get_os()
    if os_name == "linux":
        return "/dev/video0"
    if os_name == "windows":
        return "video=0"  # DirectShow
    if os_name == "mac":
        return "0"  # AVFoundation device index
    return "/dev/video0"


def get_ffmpeg_camera_args() -> list:
    """
    Return ffmpeg input arguments for camera capture on current OS.

    Returns:
        list: ffmpeg arguments for camera input.
    """
    os_name = get_os()
    device = get_camera_device()
    if os_name == "linux":
        return ["-f", "v4l2", "-framerate", "30", "-video_size", "1280x720", "-i", device]
    if os_name == "windows":
        return ["-f", "dshow", "-i", f"video={device}"]
    if os_name == "mac":
        return ["-f", "avfoundation", "-framerate", "30", "-i", f"{device}:none"]
    return ["-f", "v4l2", "-framerate", "30", "-video_size", "1280x720", "-i", device]
