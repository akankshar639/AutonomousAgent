"""agent/core.py — core autonomous execution loop."""

import json
import os
import re
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_ollama import ChatOllama

from config.settings import settings
from agent.context import build_system_prompt
from agent.logger import _extract_tool_calls, _dispatch_tool, _log, _truncate
from tools.registry import get_all_tools

# Tools that complete a task in one call — stop loop immediately after these
_STOP_AFTER_TOOLS = frozenset({
    "send_outlook_email", "send_gmail", "send_teams_message",
    "schedule_teams_meeting", "schedule_google_calendar_event",
    "cancel_teams_meeting", "linkedin_send_connection_request",
    "linkedin_send_message", "record_video",
})

_llm: ChatOllama | None = None


def _get_llm() -> ChatOllama:
    """
    Return the singleton ChatOllama instance, creating it on first call.

    Returns:
        ChatOllama: Configured LLM instance.
    """
    global _llm
    if _llm is None:
        _llm = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0.1,
            num_ctx=8192,
            num_predict=4096,
        )
    return _llm


def _build_tools_prompt() -> str:
    """
    Build a tools reference section appended to the system prompt.

    Returns:
        str: Formatted tools reference string.
    """
    tools = get_all_tools()
    lines = [
        "\n\n## Available Tools",
        "Call tools by outputting JSON: {\"name\": \"tool_name\", \"arguments\": {...}}\n",
    ]
    for t in tools:
        schema = (
            t.args_schema.model_json_schema()
            if hasattr(t, "args_schema") and t.args_schema
            else {}
        )
        props = schema.get("properties", {})
        params = ", ".join(f"{k}: {v.get('type', 'any')}" for k, v in props.items())
        lines.append(f"- {t.name}({params}): {t.description.splitlines()[0]}")

    # deepagents built-in tools
    lines += [
        "- write_file(file_path: str, content: str): Write any code or text file",
        "- execute(command: str): Run any shell command. NEVER use to send emails.",
        "- read_file(file_path: str): Read a file",
        "- ls(path: str): List directory contents",
        "- write_todos(todos: list): Plan your steps",
        "",
        "RULE: send_outlook_email(to, subject, body, cc) — pass NAMES not email addresses.",
        "RULE: send_teams_message(recipient, message) — NEVER use smtplib.",
        "RULE: NEVER write Python scripts to call tools. Call tools directly.",
        "RULE: When user says redesign or match this image: call read_image_and_describe(image_path) FIRST to understand the design, then read_file to read existing code, then write_file to update it.",
    ]
    return "\n".join(lines)


def _intercept_email_script(name: str, args: dict, result: str) -> str:
    """
    Detect when the model wrote a Python script containing send_outlook_email
    and execute the email tool directly instead.

    Args:
        name: Tool name that was called.
        args: Tool arguments dict.
        result: Result from the tool execution.

    Returns:
        str: Email result if intercepted, original result otherwise.
    """
    if name not in {"write_file", "create_file"}:
        return result
    if not result.startswith("written"):
        return result

    file_path = args.get("file_path", "")
    file_content = args.get("content", "")

    if not file_path.endswith(".py") or "send_outlook_email" not in file_content:
        return result

    body_match = re.search(r'body\s*=\s*"""([\s\S]+?)"""', file_content)
    if not body_match:
        body_match = re.search(r"body\s*=\s*'''([\s\S]+?)'''", file_content)
    to_match = re.search(r"to\s*=\s*['\"]([^'\"]+)", file_content)
    cc_match = re.search(r"cc\s*=\s*['\"]([^'\"]+)", file_content)
    subj_match = re.search(r"subject\s*=\s*'([^']+)'", file_content)

    if not (body_match and to_match):
        return result

    from skills.communication import send_outlook_email
    email_result = send_outlook_email.invoke({
        "to": to_match.group(1),
        "subject": subj_match.group(1) if subj_match else "Message",
        "body": body_match.group(1).strip(),
        "cc": cc_match.group(1) if cc_match else "",
    })
    _log.info("[INTERCEPTED→EMAIL] %s", email_result)

    try:
        os.remove(file_path)
    except OSError:
        pass

    return email_result


def run_task(task: str, thread_id: str = "default") -> str:
    """
    Run a user task through the autonomous multi-step execution loop.

    Args:
        task: Natural language task description from the user.
        thread_id: Session ID for memory continuity.

    Returns:
        str: Final response after task completion.
    """
    llm = _get_llm()
    system = build_system_prompt() + _build_tools_prompt()
    messages = [
        SystemMessage(content=system),
        HumanMessage(content=task),
    ]

    for step in range(1, settings.max_iterations + 1):
        response = llm.invoke(messages)
        content = response.content or ""

        if hasattr(response, "tool_calls") and response.tool_calls:
            tool_calls = [
                {"name": tc["name"], "arguments": tc.get("args", {})}
                for tc in response.tool_calls
            ]
        else:
            tool_calls = _extract_tool_calls(content)

        if not tool_calls:
            _log.info("[DONE] %s", _truncate(content))
            return content

        if all(
            (tc.get("name") or tc.get("action") or "") in {"write_file", "create_file", "edit_file"}
            for tc in tool_calls
        ) and all(
            len((tc.get("arguments") or tc.get("args") or tc.get("parameters") or {}).get("content", "")) > 50
            for tc in tool_calls
        ):
            results = []
            for tc in tool_calls:
                name = tc.get("name") or tc.get("action") or ""
                args = tc.get("arguments") or tc.get("args") or tc.get("parameters") or {}
                _log.info("[TOOL CALL] %s | %s", name, _truncate(json.dumps(args, ensure_ascii=False)))
                result = _dispatch_tool(name, args)
                _log.info("[TOOL RESULT] %s | %s", name, _truncate(result))
                results.append(f"Tool: {name}\nResult: {result}")
            messages.append(AIMessage(content=content))
            messages.append(HumanMessage(content=(
                f"Tool results:\n{chr(10).join(results)}\n\n"
                "Files written. If there are more files to write (e.g. styles.css, script.js), "
                "write them now using write_file. Otherwise confirm task is done."
            )))
            continue


        non_todo = [tc for tc in tool_calls if (tc.get("name") or "") != "write_todos"]
        if not non_todo and step > 1:
            _log.info("[DONE] Task completed.")
            return content or "Task completed."

        if not non_todo and step == 1:
            todos = []
            for tc in tool_calls:
                a = tc.get("arguments") or tc.get("args") or {}
                todos = a.get("todos", []) if isinstance(a, dict) else a
            messages.append(AIMessage(content=content))
            messages.append(HumanMessage(content=(
                f"Plan noted: {', '.join(str(t) for t in todos)}\n\n"
                "Now EXECUTE. Call the actual tool directly with JSON. "
                "Do NOT output write_todos again."
            )))
            continue

        results = []
        all_failed = True

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
            if not name or name == "write_todos":
                continue

            _log.info("[TOOL CALL] %s | %s", name, _truncate(json.dumps(args, ensure_ascii=False)))
            result = _dispatch_tool(name, args)
            result = _intercept_email_script(name, args, result)
            _log.info("[TOOL RESULT] %s | %s", name, _truncate(result))

            results.append(f"Tool: {name}\nResult: {result}")
            if not result.startswith("unknown tool"):
                all_failed = False

            if name in _STOP_AFTER_TOOLS and not result.lower().startswith("error"):
                _log.info("[DONE] %s", _truncate(result))
                return result

        if not results:
            _log.info("[DONE] Task completed.")
            return content or "Task completed."

        if all_failed:
            _log.info("[DONE] Required tools not available.")
            return "Task could not be completed — required tools not available."

        messages.append(AIMessage(content=content))
        messages.append(HumanMessage(content=(
            f"Tool results:\n{chr(10).join(results)}\n\n"
            "If task is complete, give the final answer directly. "
            "Do NOT call write_todos. Do NOT write Python scripts. "
            "Call tools directly with JSON."
        )))

    return "Task completed."
