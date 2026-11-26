"""Async wrapper around Firecrawl /v2/scrape (desktop, JS-rendered, body content only)."""
from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = logging.getLogger(__name__)


class FirecrawlError(RuntimeError):
    pass


EXCLUDE_TAGS = [
    "nav", "header", "footer", "aside", "noscript", "iframe", "svg",
    "#cookie-banner", ".cookie-banner", "#onetrust-consent-sdk", ".cookie-notice",
    ".newsletter", ".breadcrumbs", ".breadcrumb", ".mega-menu", ".site-header", ".site-footer",
    ".related-products", ".upsell", ".crosssell", ".recently-viewed", "#chat-widget", ".chat-widget",
]


def scrape_payload(
    url: str,
    *,
    wait_for_ms: int,
    timeout_ms: int,
    proxy: str = "auto",
    only_main_content: bool = True,
) -> dict[str, Any]:
    return {
        "url": url,
        "formats": ["markdown", "rawHtml"],
        "onlyMainContent": only_main_content,
        "excludeTags": EXCLUDE_TAGS,
        "mobile": False,
        "waitFor": wait_for_ms,
        "timeout": timeout_ms,
        "blockAds": True,
        "removeBase64Images": True,
        "proxy": proxy,
        "maxAge": 0,
        "parsers": ["pdf"],
    }


class FirecrawlClient:
    BASE_URL = "https://api.firecrawl.dev/v2"

    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.firecrawl_api_key
        self.wait_for_ms = settings.firecrawl_wait_for_ms
        self.timeout_ms = settings.firecrawl_timeout_ms

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def scrape(
        self,
        url: str,
        *,
        proxy: str = "auto",
        only_main_content: bool = True,
        stealth_on_fail: bool = True,
    ) -> dict[str, Any]:
        if not self.configured:
            raise FirecrawlError("FIRECRAWL_API_KEY is not configured")

        try:
            return await self._scrape_once(url, proxy=proxy, only_main_content=only_main_content)
        except FirecrawlError as exc:
            if stealth_on_fail and proxy != "stealth":
                logger.warning("Firecrawl retry with stealth for %s: %s", url, exc)
                return await self._scrape_once(url, proxy="stealth", only_main_content=only_main_content)
            raise

    async def _scrape_once(
        self,
        url: str,
        *,
        proxy: str,
        only_main_content: bool,
    ) -> dict[str, Any]:
        payload = scrape_payload(
            url,
            wait_for_ms=self.wait_for_ms,
            timeout_ms=self.timeout_ms,
            proxy=proxy,
            only_main_content=only_main_content,
        )
        headers = {"Authorization": f"Bearer {self.api_key}"}
        http_timeout = self.timeout_ms / 1000 + 30

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(2),
            wait=wait_exponential(min=2, max=10),
            retry=retry_if_exception_type(httpx.HTTPError),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(timeout=http_timeout) as client:
                    response = await client.post(f"{self.BASE_URL}/scrape", json=payload, headers=headers)
                if response.status_code >= 400:
                    raise FirecrawlError(
                        f"Firecrawl scrape failed for {url}: {response.status_code} {response.text[:300]}"
                    )
                data = response.json()
                # Normalise v2 envelope
                if isinstance(data.get("data"), dict):
                    return data["data"]
                return data
        raise FirecrawlError(f"Firecrawl scrape exhausted retries for {url}")


def extract_markdown_html(data: dict[str, Any]) -> tuple[str, str, str]:
    """Return (markdown, html, title) from a Firecrawl scrape payload."""
    markdown = data.get("markdown") or ""
    html = data.get("rawHtml") or data.get("html") or ""
    meta = data.get("metadata") or {}
    title = meta.get("title") or meta.get("ogTitle") or ""
    return markdown, html, title
