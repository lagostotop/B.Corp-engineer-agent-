"""
Central configuration for Brain 3.0.

All application configuration should eventually come through this module.
Secrets are read from environment variables and are never exposed to the
frontend.
"""

import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv


load_dotenv()


def _csv(value: str, default: str = "") -> List[str]:
    """Convert a comma-separated environment variable into a clean list."""
    raw = value if value is not None else default
    return [item.strip() for item in raw.split(",") if item.strip()]


def _int_env(name: str, default: int) -> int:
    """Read an integer environment variable safely."""
    value = os.getenv(name)

    if value is None or value.strip() == "":
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(
            f"Environment variable {name!r} must be an integer."
        ) from exc


@dataclass(frozen=True)
class Settings:
    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    app_name: str = os.getenv("APP_NAME", "Brain 3.0")
    environment: str = os.getenv("FLASK_ENV", "production")
    port: int = _int_env("PORT", 10000)

    # ------------------------------------------------------------------
    # Security / CORS
    # ------------------------------------------------------------------
    allowed_origins: List[str] = None

    # ------------------------------------------------------------------
    # Supabase
    # ------------------------------------------------------------------
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_service_role_key: str = os.getenv(
        "SUPABASE_SERVICE_ROLE_KEY", ""
    )
    supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")

    # ------------------------------------------------------------------
    # AI providers
    # ------------------------------------------------------------------
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    jina_api_key: str = os.getenv("JINA_API_KEY", "")

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    redis_url: str = os.getenv("REDIS_URL", "")

    # ------------------------------------------------------------------
    # Models
    # ------------------------------------------------------------------
    groq_fast_model: str = os.getenv(
        "GROQ_FAST_MODEL",
        "llama-3.1-8b-instant",
    )
    groq_general_model: str = os.getenv(
        "GROQ_GENERAL_MODEL",
        "llama-3.3-70b-versatile",
    )
    groq_reasoning_model: str = os.getenv(
        "GROQ_REASONING_MODEL",
        "llama-3.3-70b-versatile",
    )
    groq_vision_model: str = os.getenv(
        "GROQ_VISION_MODEL",
        "llama-3.2-11b-vision-preview",
    )

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL",
        "text-embedding-3-small",
    )
    embedding_dimensions: int = _int_env(
        "EMBEDDING_DIMENSIONS",
        1536,
    )

    # ------------------------------------------------------------------
    # Upload / request limits
    # ------------------------------------------------------------------
    max_upload_bytes: int = _int_env(
        "MAX_UPLOAD_BYTES",
        10 * 1024 * 1024,
    )
    request_timeout_seconds: int = _int_env(
        "REQUEST_TIMEOUT_SECONDS",
        120,
    )

    def validate(self) -> None:
        """Validate settings required to run Brain 3.0."""

        required = {
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_SERVICE_ROLE_KEY": self.supabase_service_role_key,
            "GROQ_API_KEY": self.groq_api_key,
        }

        missing = [
            name for name, value in required.items()
            if not value
        ]

        if missing:
            raise RuntimeError(
                "Missing required environment variables: "
                + ", ".join(missing)
            )

        if self.environment == "production":
            if not self.supabase_url.startswith("https://"):
                raise RuntimeError(
                    "SUPABASE_URL must use HTTPS in production."
                )

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


settings = Settings(
    allowed_origins=_csv(
        os.getenv("ALLOWED_ORIGINS"),
        "*",
    )
)
