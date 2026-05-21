"""skills/filesystem.py — custom file tools extending deepagents built-ins."""

from pathlib import Path

from docx import Document
from langchain_core.tools import tool


@tool
def create_docx(file_path: str, content: str) -> str:
    """
    Create a proper Microsoft Word .docx file at the given absolute path.

    Use this tool whenever the user asks to create a .docx or Word document.
    Do NOT use write_file for .docx — it only writes plain text.
    This tool uses python-docx to create a real Word document.

    Each blank line in content becomes a paragraph break in the document.

    Args:
        file_path: Absolute path where the .docx file should be saved.
                   Example: /home/sparkbrains/Desktop/hello.docx
        content: Full text content to write into the Word document.
                 Write the COMPLETE content — do not truncate or summarize.

    Returns:
        str: Confirmation message with the file path.
    """
    path = Path(file_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = Document()
    for para in content.split("\n"):
        doc.add_paragraph(para)

    doc.save(str(path))
    return f"Word document created successfully: {file_path}"
