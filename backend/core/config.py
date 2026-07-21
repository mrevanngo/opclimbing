"""Application configuration. Loads .env; no secrets live in source (CLAUDE.md)."""

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    anthropic_api_key: str
    port: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings from the environment (and backend/.env if present).

    Raises a clear error for missing required values rather than failing
    later with a confusing downstream exception.
    """
    load_dotenv()

    missing: list[str] = []

    def require(name: str) -> str:
        value = os.environ.get(name, "")
        if not value:
            missing.append(name)
        return value

    settings = Settings(
        database_url=require("DATABASE_URL"),
        jwt_secret=require("JWT_SECRET"),
        anthropic_api_key=require("ANTHROPIC_API_KEY"),
        port=int(os.environ.get("PORT", "8080")),
    )
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Copy backend/.env.example to backend/.env and fill in the values."
        )
    return settings
