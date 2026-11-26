from __future__ import annotations

import logging

from app.adapters.dataforseo_client import DataForSeoClient
from app.adapters.search_types import SearchLocale, SearchProviderError, SearchResponse
from app.adapters.serper_client import SerperClient

logger = logging.getLogger(__name__)


async def search_organic(query: str, locale: SearchLocale | None = None, *, num: int = 15) -> SearchResponse:
    locale = locale or SearchLocale()
    errors: list[str] = []

    serper = SerperClient()
    if serper.configured:
        try:
            return await serper.search(query, locale, num=num)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"serper: {exc}")
            logger.warning("Serper failed: %s", exc)

    dfs = DataForSeoClient()
    if dfs.configured:
        try:
            return await dfs.search(query, locale, num=num)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"dataforseo: {exc}")
            logger.warning("DataForSEO failed: %s", exc)

    raise SearchProviderError("No search provider succeeded: " + "; ".join(errors or ["none configured"]))
