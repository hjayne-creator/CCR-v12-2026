"""Extract competitor-name tokens for STY-003 / FAQ-001 body checks.

Avoids false positives like fuel type ("Petrol") taken from titles of the same
client product sold on retailer / review sites.
"""
from __future__ import annotations

import re
from typing import Iterable

from app.adapters.search_types import domain_of

# Marketplace / infra domains — not useful as "competitor brand" mentions in copy.
_SKIP_DOMAIN_ROOTS = {
    "www", "http", "https", "com", "co", "uk", "org", "net",
    "amazon", "ebay", "google", "facebook", "youtube", "wikipedia",
    "pricerunner", "feefo", "trustpilot", "reddit", "example", "test",
    "diy",  # B&Q diy.com — too short/ambiguous as a body-copy brand token
}

# Product descriptors / fuels / units — never treat as competitor brands.
_GENERIC_TOKENS = {
    "www", "http", "https", "com", "co", "uk", "the", "and", "for", "with", "from",
    "low", "high", "new", "pro", "set", "kit", "pack", "pair", "size", "model",
    "profile", "garage", "trolley", "jack", "tonne", "ton", "cc", "inch", "inches",
    "capacity", "height", "width", "length", "weight", "steel", "aluminium", "aluminum",
    "tools", "tool", "product", "products", "shop", "store", "official", "example", "test",
    "petrol", "diesel", "electric", "cordless", "battery", "gas", "oil", "hydraulic",
    "pneumatic", "manual", "automatic", "recoil", "chainsaw", "saw", "bar", "chain",
    "oregon", "premium", "powerful", "portable", "compact", "heavy", "duty",
    "reviews", "review", "best", "price", "see", "buy", "online", "delivery",
    "customer", "feedback", "well", "balanced", "simple", "easy", "start",
    # Company / site chrome often appears after "|" in retailer/review titles
    "engineering", "engineers", "limited", "ltd", "plc", "inc", "corp", "company",
    "group", "holdings", "international", "uk", "usa",
}


def _normalize_token(tok: str) -> str:
    return re.sub(r"[^a-z0-9&]", "", (tok or "").lower())


def _subject_blocked_tokens(
    *,
    subject_title: str,
    owned_brands: Iterable[str] | None,
    subject_domain: str = "",
) -> set[str]:
    blocked = set(_GENERIC_TOKENS)
    for brand in owned_brands or []:
        b = _normalize_token(brand)
        if b:
            blocked.add(b)
        # also block space-split parts (e.g. "SGS Engineering" → sgs, engineering)
        for part in re.findall(r"[A-Za-z0-9]+", brand):
            blocked.add(part.lower())
    for tok in re.findall(r"[A-Za-z][A-Za-z0-9&-]{1,}", subject_title or ""):
        blocked.add(_normalize_token(tok))
    if subject_domain:
        root = (domain_of(f"https://{subject_domain}") or subject_domain).split(".")[0]
        if root:
            blocked.add(_normalize_token(root.replace("-", "")))
            blocked.add(_normalize_token(root))
    return {t for t in blocked if t}


def extract_competitor_name_tokens(
    *,
    competitor_sources: list[dict],
    subject_title: str = "",
    owned_brands: Iterable[str] | None = None,
    subject_domain: str = "",
) -> list[str]:
    """Return brand-like tokens that may appear in PDP body copy as competitor mentions.

    Each competitor_sources item: {domain?, title?}
    """
    blocked = _subject_blocked_tokens(
        subject_title=subject_title,
        owned_brands=owned_brands,
        subject_domain=subject_domain,
    )

    found: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        key = _normalize_token(raw)
        if not key or len(key) < 4:
            return
        if key in blocked or key in _SKIP_DOMAIN_ROOTS or key in _GENERIC_TOKENS:
            return
        if key in seen:
            return
        # Avoid pure numeric / cc codes
        if key.isdigit():
            return
        seen.add(key)
        found.append(raw if raw[0].isupper() else raw.capitalize())

    for src in competitor_sources:
        domain = (src.get("domain") or "").lower()
        title = src.get("title") or ""
        if domain:
            host = domain_of(f"https://{domain}") or domain
            root = host.split(".")[0]
            # Keep hyphenated brand roots as one token without hyphens for matching
            add(root.replace("-", ""))
            if "-" in root:
                add(root.split("-")[0])

        # Title tokens: only Title-case words that are not subject/generic.
        # Skip ALL-CAPS (SGS) and lowercase glue words.
        for tok in re.findall(r"[A-Za-z][A-Za-z0-9&-]{2,}", title):
            if tok.isupper():
                continue
            if not tok[0].isupper():
                continue
            if _normalize_token(tok) in blocked:
                continue
            add(tok)
            break  # one brand-like token per title is enough

    return found
