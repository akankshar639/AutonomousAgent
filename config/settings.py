"""config/settings.py — centralized configuration loaded from .env."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_PROJECT_ROOT = Path(__file__).parent.parent


class Settings:
    """
    Typed configuration container loaded from environment variables.

    All path defaults are cross-platform. Override any value via .env.
    """

    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
    litellm_model: str = os.getenv("LITELLM_MODEL", "ollama/qwen2.5-coder:7b")
    vision_model: str = os.getenv("VISION_MODEL", "llava:7b")

    sandbox_workdir: Path = Path(
        os.getenv("SANDBOX_WORKDIR", str(_PROJECT_ROOT / "sandbox_workdir"))
    )
    sandbox_timeout: int = int(os.getenv("SANDBOX_TIMEOUT", "120"))

    checkpoint_db_path: Path = Path(
        os.getenv("CHECKPOINT_DB_PATH", str(_PROJECT_ROOT / "memory" / "checkpoints.db"))
    )

    max_iterations: int = int(os.getenv("MAX_ITERATIONS", "20"))
    agents_md_path: Path = Path(
        os.getenv("AGENTS_MD_PATH", str(_PROJECT_ROOT / "AGENTS.md"))
    )

    @classmethod
    def ensure_dirs(cls) -> None:
        """Create all required runtime directories if they do not exist."""
        cls.sandbox_workdir.mkdir(parents=True, exist_ok=True)
        cls.checkpoint_db_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
