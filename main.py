"""main.py — CLI entry point for the Fully Autonomous Local Agent."""

import uuid
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from config.settings import settings
from agent.core import run_task


def _enrich_task(task: str) -> str:
    """
    Enrich the user task with explicit tool routing instructions.

    Args:
        task: Raw user task string.

    Returns:
        str: Enriched task string with routing hints appended.
    """
    t = task.lower()

    email_keywords = ["mail", "email", "outlook", "gmail", "send to", "write to", "cc "]
    redesign_keywords = ["redesign", "match this image", "make it look like", "refer to this image",
                         "match the reference", "match reference", "look like"]
    code_keywords = ["code", "script", "program", "calculator", "python", "javascript",
                     "html", "css", "function", "class", "implement", "build", "develop",
                     "create a project", "write a", "full fledge"]
    doc_keywords = ["docx", "document", "story", "essay", "poem", "notes", "report", "letter"]

    is_email = any(k in t for k in email_keywords)
    is_redesign = any(k in t for k in redesign_keywords)
    is_code = any(k in t for k in code_keywords)
    is_doc = any(k in t for k in doc_keywords)

    # Email takes highest priority — never override with code/doc instruction
    if is_email:
        return (
            task + "\n\n"
            "[INSTRUCTION] This is an EMAIL task. "
            "Call send_outlook_email(to, subject, body, cc) directly with JSON. "
            "Write the full email body as the 'body' argument. "
            "Do NOT use write_file. Do NOT create any file. Just call send_outlook_email."
        )

    # Redesign takes priority over code instruction
    if is_redesign:
        return task

    if is_code and not is_doc:
        return (
            task + "\n\n"
            "[INSTRUCTION] This is a CODE task. "
            "Use execute() to create directories and write_file() to write each code file (.py, .html, .css, .js). "
            "Do NOT use create_docx. Write actual runnable code files."
        )

    if is_doc and not is_code:
        return (
            task + "\n\n"
            "[INSTRUCTION] This is a DOCUMENT task. "
            "Use create_docx() to create a .docx file with the full content."
        )

    return task

app = typer.Typer(help="Fully Autonomous Local Agent — powered by Ollama + Deep Agents")
console = Console()


@app.command()
def chat(
    thread_id: str = typer.Option(
        None,
        "--thread",
        "-t",
        help="Session thread ID for memory continuity. Auto-generated if not provided.",
    )
) -> None:
    """
    Start an interactive session with the autonomous agent.
    Type your task and press Enter. The agent handles everything.
    Type 'exit' or 'quit' to end the session.
    """
    settings.ensure_dirs()
    session_id = thread_id or str(uuid.uuid4())[:8]

    console.print(
        Panel(
            f"[bold green]Autonomous Agent[/bold green] — Local | Ollama | Deep Agents\n"
            f"Model: [cyan]{settings.litellm_model}[/cyan] | Session: [yellow]{session_id}[/yellow]\n"
            "Type your task. Type [red]exit[/red] to quit.",
            title="Fully Autonomous Agent",
        )
    )

    while True:
        try:
            task = Prompt.ask("\n[bold blue]You[/bold blue]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Session ended.[/yellow]")
            break

        if task.lower() in {"exit", "quit", "q"}:
            console.print("[yellow]Goodbye.[/yellow]")
            break

        if not task:
            continue

        console.print("[dim]Agent is working...[/dim]")
        try:
            response = run_task(_enrich_task(task), thread_id=session_id)
            console.print(Panel(response, title="[bold green]Agent[/bold green]", border_style="green"))
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")


@app.command()
def run(
    task: str = typer.Argument(..., help="Task to execute."),
    thread_id: str = typer.Option("default", "--thread", "-t", help="Session thread ID."),
) -> None:
    """
    Run a single task non-interactively and print the result.
    """
    settings.ensure_dirs()
    console.print(f"[dim]Running task: {task}[/dim]")
    try:
        response = run_task(task, thread_id=thread_id)
        console.print(Panel(response, title="[bold green]Result[/bold green]", border_style="green"))
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
