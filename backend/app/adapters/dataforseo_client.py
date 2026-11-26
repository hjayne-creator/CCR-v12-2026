"""DataForSEO Google Organic live client (fallback when Serper unavailable)."""
from __future__ import annotations

import base64
import re
from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.adapters.search_types import OrganicResult, SearchLocale, SearchProviderError, SearchResponse, domain_of
from app.config import get_settings


def parse_credentials(raw: str | None) -> tuple[str, str] | None:
    if not raw:
        return None
    raw = raw.strip()
    for sep in (" / ", "/", ":"):
        if sep in raw:
            login, _, password = raw.partition(sep)
            if login.strip() and password.strip():
                return login.strip(), password.strip()
    parts = re.split(r"\s+", raw)
    if len(parts) == 2:
        return parts[0], parts[1]
    return None


class DataForSeoClient:
    name = "dataforseo"
    URL = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"

    def __init__(self, credentials: str | None = None, timeout: float = 60.0) -> None:
        settings = get_settings()
        self.creds = parse_credentials(credentials or settings.resolved_dataforseo_credentials)
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.creds)

    async def search(self, query: str, locale: SearchLocale, *, num: int = 20) -> SearchResponse:
        if not self.configured or not self.creds:
            raise SearchProviderError("DATAFORSEO_CREDENTIALS is not configured")
        login, password = self.creds
        token = base64.b64encode(f"{login}:{password}".encode()).decode()
        payload = [
            {
                "keyword": query,
                "location_name": locale.location_name,
                "language_code": locale.hl,
                "device": "desktop",
                "os": "windows",
                "depth": num,
            }
        ]
        headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(min=1, max=8),
            retry=retry_if_exception_type(httpx.HTTPError),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(self.URL, json=payload, headers=headers)
                if response.status_code >= 400:
                    raise SearchProviderError(f"DataForSEO {response.status_code}: {response.text[:300]}")
                data = response.json()
        results: list[OrganicResult] = []
        try:
            items = data["tasks"][0]["result"][0].get("items") or []
        except (KeyError, IndexError, TypeError) as exc:
            raise SearchProviderError(f"DataForSEO unexpected payload: {str(data)[:200]}") from exc
        for item in items:
            if item.get("type") != "organic":
                continue
            url = item.get("url") or ""
            if not url or url in {x.url for x in results}:
                continue
            results.append(
                OrganicResult(
                    position=len(results) + 1,
                    absolute_rank=item.get("rank_absolute"),
                    title=item.get("title") or "",
                    url=url,
                    domain=domain_of(url),
                    snippet=item.get("description") or "",
                )
            )
        if not results:
            raise SearchProviderError("DataForSEO returned no organic results")
        return SearchResponse(
            query=query,
            provider=self.name,
            rank_source="google_organic",
            results=results[:num],
            raw={"status_code": data.get("status_code")},
        )
