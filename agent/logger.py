"""agent/logger.py — terminal logger and tool dispatcher."""

import json
import re
import logging
import subprocess
from pathlib import Path


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def get_logger(agent_name: str, module_name: str = "") -> logging.Logger:
    """
    Return a logger for the given agent and optional sub-module.

    Args:
        agent_name: Top-level agent name.
        module_name: Sub-module name appended as agent_name.module_name if provided.

    Returns:
        logging.Logger: Configured logger instance.
    """
    name = agent_name if not module_name else f"{agent_name}.{module_name}"
    return logging.getLogger(name)


_log = get_logger("autonomous_agent")


def _truncate(text: str, limit: int = 300) -> str:
    """
    Truncate text to limit characters for clean terminal display.

    Args:
        text: Input string.
        limit: Maximum character count.

    Returns:
        str: Truncated string with '...' suffix if over limit.
    """
    return text if len(text) <= limit else text[:limit] + "..."


def _extract_tool_calls(text: str) -> list[dict]:
    """
    Extract tool call JSON objects from model plain-text response.

    Handles three formats in priority order:
        1. <tool_call>...</tool_call> XML tags
        2. ```json ... ``` code blocks
        3. Bare JSON object in response

    Args:
        text: Raw model response string.

    Returns:
        list[dict]: Parsed tool call dicts.
    """
    results = []

    for match in re.finditer(r"<tool_call>(.*?)</tool_call>", text, re.DOTALL):
        try:
            results.append(json.loads(match.group(1).strip()))
        except json.JSONDecodeError:
            pass

    if not results:
        for match in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL):
            try:
                results.append(json.loads(match.group(1).strip()))
            except json.JSONDecodeError:
                pass

    if not results:
        match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
        if match:
            try:
                results.append(json.loads(match.group().strip()))
            except json.JSONDecodeError:
                pass

    return results


def _dispatch_file_tool(name: str, arguments: dict) -> str | None:
    """
    Handle file system tool calls: execute, write_file, create_docx, read_file, ls.

    Args:
        name: Normalized tool name.
        arguments: Tool arguments dict.

    Returns:
        str | None: Result string if handled, None if not a file tool.
    """
    if any(x in name for x in ["execute", "shell", "bash", "run", "cmd", "command"]):
        command = arguments.get("command") or arguments.get("cmd") or arguments.get("shell")
        if command:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=120
            )
            out = result.stdout or ""
            if result.returncode != 0:
                out += f"\nERROR (exit {result.returncode}): {result.stderr}"
            elif result.stderr:
                out += f"\nstderr: {result.stderr}"
            return out.strip() or "done"

    if any(x in name for x in ["write_file", "create_file", "save_file"]) and "docx" not in name:
        path_str = arguments.get("file_path") or arguments.get("path") or arguments.get("filename")
        content = arguments.get("content") or arguments.get("code") or ""
        if path_str:
            path = Path(path_str)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            last_line = content.rstrip().splitlines()[-1] if content.strip() else ""
            truncated = content.strip() and not any(last_line.strip().endswith(c) for c in [
                "}", "</html>", "</style>", "</script>", ";", "\"\"\"\n", "'", "#"
            ])
            suffix = " (WARNING: content may be truncated — check file)" if truncated else ""
            return f"written: {path_str}{suffix}"

    if "docx" in name or name == "create_doc":
        path_str = arguments.get("file_path") or arguments.get("path")
        content = arguments.get("content", "")
        if path_str:
            from docx import Document
            path = Path(path_str)
            path.parent.mkdir(parents=True, exist_ok=True)
            doc = Document()
            for para in content.split("\n"):
                doc.add_paragraph(para)
            doc.save(str(path))
            return f"docx created: {path_str}"

    if name == "read_file":
        path_str = arguments.get("file_path") or arguments.get("path", "")
        try:
            return Path(path_str).read_text(encoding="utf-8")
        except Exception as e:
            return f"read error: {e}"

    if name in {"ls", "list_directory", "list_dir"}:
        path_str = arguments.get("path", ".")
        result = subprocess.run(f"ls {path_str}", shell=True, capture_output=True, text=True)
        return result.stdout

    return None


def _dispatch_browser_tool(name: str, arguments: dict) -> str | None:
    """
    Handle browser automation tool calls via Playwright.

    Args:
        name: Normalized tool name.
        arguments: Tool arguments dict.

    Returns:
        str | None: Result string if handled, None if not a browser tool.
    """
    from skills.browser import _get_page, close_browser, wait_for_login

    _browser_map = {
        "open_url": lambda a: _get_page().goto(a.get("url", ""), wait_until="domcontentloaded", timeout=30000) or f"opened: {a.get('url')}",
        "get_page_text": lambda a: _get_page().inner_text("body")[:3000],
        "get_current_url": lambda a: _get_page().url,
        "close_browser_session": lambda a: (close_browser(), "browser closed")[1],
    }

    if name in _browser_map:
        try:
            return _browser_map[name](arguments)
        except Exception as e:
            return f"{name} error: {e}"

    if name == "click_element":
        selector = arguments.get("selector", "")
        try:
            _get_page().click(selector, timeout=10000)
            return f"clicked: {selector}"
        except Exception as e:
            return f"click_element error: {e}"

    if name == "fill_field":
        try:
            _get_page().fill(arguments.get("selector", ""), arguments.get("value", ""))
            return f"filled: {arguments.get('selector')}"
        except Exception as e:
            return f"fill_field error: {e}"

    if name in {"wait_for_element", "wait_for_selector"}:
        try:
            _get_page().wait_for_selector(arguments.get("selector", ""), timeout=int(arguments.get("timeout", 10)) * 1000)
            return f"element appeared: {arguments.get('selector')}"
        except Exception as e:
            return f"wait_for_element error: {e}"

    if name in {"browser_press_key", "press_key_browser"}:
        try:
            _get_page().keyboard.press(arguments.get("key", "Enter"))
            return f"pressed: {arguments.get('key')}"
        except Exception as e:
            return f"browser_press_key error: {e}"

    if name == "wait_for_login":
        return wait_for_login.invoke(arguments)

    return None


def _dispatch_skill_tool(name: str, arguments: dict) -> str | None:
    """
    Handle skill-based tool calls: communication, calendar, desktop, uitars, media.

    Args:
        name: Normalized tool name.
        arguments: Tool arguments dict.

    Returns:
        str | None: Result string if handled, None if not a skill tool.
    """
    import importlib

    _skill_map = {
        "cancel_teams_meeting": "skills.communication",
        "send_teams_message": "skills.communication",
        "send_outlook_email": "skills.communication",
        "send_gmail": "skills.communication",
        "linkedin_send_connection_request": "skills.communication",
        "linkedin_send_message": "skills.communication",
        "search_web": "skills.communication",
        "open_camera_and_capture": "skills.communication",
        "record_video": "skills.communication",
        "send_teams_file": "skills.communication",
        "read_image_and_describe": "skills.communication",
        "schedule_teams_meeting": "skills.calendar_skill",
        "schedule_google_calendar_event": "skills.calendar_skill",
        "schedule_google_meet": "skills.calendar_skill",
        "take_screenshot": "skills.desktop",
        "click_on_screen": "skills.desktop",
        "double_click_on_screen": "skills.desktop",
        "type_text": "skills.desktop",
        "press_key": "skills.desktop",
        "find_and_click_image": "skills.desktop",
        "open_application": "skills.desktop",
        "scroll": "skills.desktop",
        "uitars_act": "skills.uitars",
        "uitars_screenshot_and_describe": "skills.uitars",
        "transcribe_video": "skills.media",
        "extract_document_text": "skills.media",
    }

    module_path = _skill_map.get(name)
    if module_path:
        fn_name = "schedule_google_calendar_event" if name == "schedule_google_meet" else name
        mod = importlib.import_module(module_path)
        fn = getattr(mod, fn_name, None)
        if fn:
            return fn.invoke(arguments)

    if name == "write_todos":
        todos = arguments.get("todos", []) if isinstance(arguments, dict) else arguments
        if isinstance(todos, list):
            return "planned: " + ", ".join(str(t) for t in todos)
        return "planned: " + str(todos)

    return None


def _dispatch_tool(name: str, arguments: dict) -> str:
    """
    Route a tool name to its implementation and execute it.

    Args:
        name: Tool name string (normalized to lowercase with underscores).
        arguments: Tool arguments dict.

    Returns:
        str: Execution result message.
    """
    name = name.lower().replace("-", "_").replace(" ", "_")

    result = _dispatch_file_tool(name, arguments)
    if result is not None:
        return result

    result = _dispatch_browser_tool(name, arguments)
    if result is not None:
        return result

    result = _dispatch_skill_tool(name, arguments)
    if result is not None:
        return result

    return f"unknown tool: {name}"


def stream_agent_events(agent, input_messages: dict, config: dict) -> str:
    """
    Stream deepagents graph execution events to terminal in real time.

    Args:
        agent: Compiled deepagents graph.
        input_messages: Input dict with 'messages' key.
        config: LangGraph thread config dict.

    Returns:
        str: Final agent response string.
    """
    final_response = ""
    tool_was_called = False

    for event in agent.stream(input_messages, config=config, stream_mode="values"):
        messages = event.get("messages", [])
        if not messages:
            continue

        last = messages[-1]
        msg_type = type(last).__name__

        if msg_type == "AIMessage":
            if hasattr(last, "tool_calls") and last.tool_calls:
                tool_was_called = True
                for tc in last.tool_calls:
                    _log.info(
                        "[TOOL CALL] %s | %s",
                        tc.get("name", "unknown"),
                        _truncate(json.dumps(tc.get("args", {}), ensure_ascii=False)),
                    )
            elif last.content:
                final_response = last.content

        elif msg_type == "ToolMessage":
            _log.info("[TOOL RESULT] %s | %s", last.name, _truncate(str(last.content)))

    if not tool_was_called and final_response:
        tool_calls = _extract_tool_calls(final_response)
        if tool_calls:
            for tc in tool_calls:
                name = (
                    tc.get("name")
                    or tc.get("action")
                    or tc.get("function", {}).get("name", "")
                )
                args = (
                    tc.get("arguments")
                    or tc.get("args")
                    or tc.get("parameters")
                    or {}
                )
                if name:
                    _log.info(
                        "[FALLBACK TOOL] %s | %s",
                        name,
                        _truncate(json.dumps(args, ensure_ascii=False)),
                    )
                    result = _dispatch_tool(name, args)
                    _log.info("[FALLBACK RESULT] %s", result)
            final_response = "Task completed."

    _log.info("[DONE] %s", _truncate(final_response))
    return final_response
