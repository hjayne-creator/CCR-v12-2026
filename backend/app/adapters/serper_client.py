from __future__ import annotations

from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.adapters.search_types import OrganicResult, SearchLocale, SearchProviderError, SearchResponse, domain_of
from app.config import get_settings


class SerperClient:
    name = "serper"
    URL = "https://google.serper.dev/search"

    def __init__(self, api_key: str | None = None, timeout: float = 30.0) -> None:
        self.api_key = api_key or get_settings().serper_api_key
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str, locale: SearchLocale, *, num: int = 20) -> SearchResponse:
        if not self.configured:
            raise SearchProviderError("SERPER_API_KEY is not configured")
        payload: dict[str, Any] = {
            "q": query,
            "gl": locale.gl,
            "hl": locale.hl,
            "location": locale.location_name,
            "num": num,
        }
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
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
                    raise SearchProviderError(f"Serper {response.status_code}: {response.text[:300]}")
                data = response.json()
        results: list[OrganicResult] = []
        for r in data.get("organic") or []:
            url = r.get("link") or ""
            if not url or url in {x.url for x in results}:
                continue
            results.append(
                OrganicResult(
                    position=len(results) + 1,
                    absolute_rank=r.get("position"),
                    title=r.get("title") or "",
                    url=url,
                    domain=domain_of(url),
                    snippet=r.get("snippet") or "",
                )
            )
        if not results:
            raise SearchProviderError(f"Serper returned no organic results: {str(data)[:200]}")
        raw = {k: data.get(k) for k in ("searchParameters", "organic", "credits")}
        return SearchResponse(
            query=query,
            provider=self.name,
            rank_source="google_organic",
            results=results[:num],
            raw=raw,
        )
