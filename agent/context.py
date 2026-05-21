"""agent/context.py — loads AGENTS.md files to build the system prompt."""

from pathlib import Path
from config.settings import settings


def _load_file(path: Path) -> str:
    """
    Read and return file content, or empty string if not found.

    Args:
        path: Path to the file.

    Returns:
        str: File content, or empty string if the file does not exist.
    """
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def build_system_prompt() -> str:
    """
    Build the full system prompt by combining global and project-level AGENTS.md.

    Returns:
        str: Combined system prompt string.
    """
    parts = []

    global_md = _load_file(settings.agents_md_path)
    if global_md:
        parts.append(global_md)

    # load project-level AGENTS.md if different from global
    project_md_path = Path.cwd() / "AGENTS.md"
    is_different = project_md_path.resolve() != settings.agents_md_path.resolve()
    if is_different:
        project_md = _load_file(project_md_path)
        if project_md:
            parts.append(f"## Project Context\n{project_md}")

    return "\n\n".join(parts)
