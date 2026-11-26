from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Project-root .env.local is the usual place; backend/.env.local also works.
        env_file=(
            _ROOT / ".env",
            _ROOT / ".env.local",
            _BACKEND / ".env",
            _BACKEND / ".env.local",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    # Alias used in CCR v2611
    claude_api_key: str = ""
    google_api_key: str = ""
    gemini_api_key: str = ""
    firecrawl_api_key: str = ""
    serper_api_key: str = ""
    dataforseo_credentials: str = ""
    # Alias used in CCR v2611
    dataforseo_api_key: str = ""

    firecrawl_wait_for_ms: int = 3000
    firecrawl_timeout_ms: int = 60000

    default_writer_provider: str = "anthropic"
    default_writer_model: str = "claude-sonnet-5-5"
    default_qa_provider: str = "openai"
    default_qa_model: str = "gpt-6.1-terra"
    default_extract_provider: str = "openai"
    default_extract_model: str = "gpt-6-luna"

    use_fixtures: bool = False
    fixture_dir: str = ""

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def sqlite_path(self) -> Path:
        return _BACKEND / "ccr.db"

    @property
    def resolved_database_url(self) -> str:
        url = self.database_url.strip()
        if not url:
            return f"sqlite:///{self.sqlite_path}"
        # Railway / Heroku often emit postgres://; SQLAlchemy + psycopg3 need postgresql+psycopg://
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql://") and "+psycopg" not in url.split("://", 1)[0]:
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        return url

    @property
    def resolved_anthropic_key(self) -> str:
        return self.anthropic_api_key or self.claude_api_key

    @property
    def resolved_google_key(self) -> str:
        return self.google_api_key or self.gemini_api_key

    @property
    def resolved_dataforseo_credentials(self) -> str:
        return self.dataforseo_credentials or self.dataforseo_api_key

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def resolved_fixture_dir(self) -> Path:
        if self.fixture_dir.strip():
            return Path(self.fixture_dir)
        return _BACKEND / "tests" / "fixtures"


@lru_cache
def get_settings() -> Settings:
    return Settings()
