from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlparse


class SearchProviderError(RuntimeError):
    pass


@dataclass
class SearchLocale:
    gl: str = "uk"
    hl: str = "en"
    google_domain: str = "google.co.uk"
    location_name: str = "United Kingdom"


@dataclass
class OrganicResult:
    position: int
    title: str
    url: str
    domain: str
    snippet: str = ""
    absolute_rank: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SearchResponse:
    query: str
    provider: str
    rank_source: str
    results: list[OrganicResult]
    raw: dict[str, Any] = field(default_factory=dict)


def domain_of(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host
