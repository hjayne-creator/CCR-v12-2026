from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, Session, SQLModel, create_engine, select

from app.config import get_settings

_engine = None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Client(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    name: str
    domain: str = ""
    client_domains: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    untrusted_domains: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    owned_brands: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    market_country: str = "uk"
    language: str = "en-GB"
    google_domain: str = "google.co.uk"
    currency: str = "GBP"
    competitor_count: int = 3
    max_words: int = 1500
    title_max_chars: int = 150
    rules_version: str = "1.0"
    settings: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class Run(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(index=True)
    url: str
    status: str = Field(default="pending", index=True)  # pending|running|completed|failed|released
    current_stage: int = 0
    error: Optional[str] = Field(default=None, sa_column=Column(Text))
    model_overrides: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    identity_class: Optional[str] = None  # Brand|Reseller
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    released: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    completed_at: Optional[datetime] = None


class StageResult(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(index=True)
    stage: int = Field(index=True)
    name: str
    status: str = "pending"  # pending|running|passed|failed|skipped
    gate: Optional[str] = None
    artifact: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    error: Optional[str] = Field(default=None, sa_column=Column(Text))
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None


class Source(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(index=True)
    url: str
    role: str  # subject|manufacturer|competitor
    domain: str = ""
    title: str = ""
    markdown: str = Field(default="", sa_column=Column(Text))
    html: str = Field(default="", sa_column=Column(Text))
    meta: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class LlmUsage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(index=True)
    stage: int = 0
    provider: str
    model: str
    role: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    created_at: datetime = Field(default_factory=utcnow)


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.resolved_database_url
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, echo=False, connect_args=connect_args)
    return _engine


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Session:
    return Session(get_engine())


def get_client_by_slug(slug: str) -> Client | None:
    with get_session() as session:
        return session.exec(select(Client).where(Client.slug == slug)).first()
