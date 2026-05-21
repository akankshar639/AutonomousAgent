"""sandbox/executor.py — isolated sandbox for running shell commands and Python code."""

import subprocess
import tempfile
import textwrap
from pathlib import Path
from dataclasses import dataclass

from config.settings import settings


@dataclass
class ExecutionResult:
    """Result of a sandbox execution."""

    stdout: str
    stderr: str
    exit_code: int
    success: bool


class SandboxExecutor:
    """
    Executes shell commands and Python code in an isolated sandbox directory.

    All operations are confined to settings.sandbox_workdir.
    """

    def __init__(self) -> None:
        """Initialize sandbox and ensure working directory exists."""
        self.workdir = settings.sandbox_workdir
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.timeout = settings.sandbox_timeout

    def run_command(self, command: str, cwd: Path | None = None) -> ExecutionResult:
        """
        Run a shell command inside the sandbox.

        Args:
            command: Shell command string to execute.
            cwd: Working directory override. Defaults to sandbox workdir.

        Returns:
            ExecutionResult: stdout, stderr, exit_code, and success flag.
        """
        work_path = cwd or self.workdir
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(work_path),
            )
            return ExecutionResult(
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                success=result.returncode == 0,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                stdout="",
                stderr=f"Command timed out after {self.timeout}s",
                exit_code=-1,
                success=False,
            )

    def run_python(self, code: str) -> ExecutionResult:
        """
        Execute a Python code snippet in the sandbox via a temp file.

        Args:
            code: Python source code string to execute.

        Returns:
            ExecutionResult: stdout, stderr, exit_code, and success flag.
        """
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            dir=self.workdir,
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(textwrap.dedent(code))
            tmp_path = Path(tmp.name)

        try:
            return self.run_command(f"python3 {tmp_path.name}")
        finally:
            tmp_path.unlink(missing_ok=True)

    def write_file(self, filename: str, content: str) -> Path:
        """
        Write a file into the sandbox working directory.

        Args:
            filename: Name of the file to create.
            content: Text content to write.

        Returns:
            Path: Absolute path of the created file.
        """
        file_path = self.workdir / filename
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def read_file(self, filename: str) -> str:
        """
        Read a file from the sandbox working directory.

        Args:
            filename: Name of the file to read.

        Returns:
            str: File content.

        Raises:
            FileNotFoundError: If the file does not exist in the sandbox.
        """
        file_path = self.workdir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"{filename} not found in sandbox.")
        return file_path.read_text(encoding="utf-8")
