"""Load offline scrape/search fixtures for CI and local dry-runs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import get_settings


def fixtures_enabled(override: bool | None = None) -> bool:
    if override is not None:
        return override
    return get_settings().use_fixtures


def fixture_dir() -> Path:
    return get_settings().resolved_fixture_dir


def load_json(name: str) -> dict[str, Any]:
    path = fixture_dir() / name
    if not path.exists():
        raise FileNotFoundError(f"Fixture missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_text(name: str) -> str:
    path = fixture_dir() / name
    if not path.exists():
        raise FileNotFoundError(f"Fixture missing: {path}")
    return path.read_text(encoding="utf-8")
