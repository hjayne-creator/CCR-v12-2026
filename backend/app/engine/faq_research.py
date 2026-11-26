"""Helpers to seed FAQ questions from research artifacts."""
from __future__ import annotations

import re
from typing import Any

from app.models.db import Source
from app.models.schemas import FactLedger

_QUESTION_RE = re.compile(
    r"(?m)^(?:#{1,3}\s*)?(?:q(?:uestion)?\s*[:.)-]\s*)?(.{8,160}\?)\s*$",
    re.I,
)
_CLAIM_TYPES_FOR_FAQ = {
    "faq_answer",
    "concern_response",
    "use_case",
    "warranty",
    "compatibility",
    "safety",
    "package_contents",
    "spec",
    "feature",
}


def extract_question_seeds(markdown: str, *, limit: int = 12) -> list[str]:
    """Pull question-like lines from scraped PDP markdown."""
    text = markdown or ""
    found: list[str] = []
    seen: set[str] = set()
    for match in _QUESTION_RE.finditer(text):
        q = re.sub(r"\s+", " ", match.group(1)).strip()
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(q)
        if len(found) >= limit:
            break
    return found


def research_faq_context(
    *,
    ledger: FactLedger,
    sources: list[Source],
    max_seeds: int = 16,
) -> dict[str, Any]:
    """Bundle research inputs the writer should use for FAQ-001."""
    seeds: list[str] = []
    seen: set[str] = set()
    for src in sources:
        for q in extract_question_seeds(src.markdown or "", limit=8):
            key = q.lower()
            if key in seen:
                continue
            seen.add(key)
            seeds.append(q)
            if len(seeds) >= max_seeds:
                break
        if len(seeds) >= max_seeds:
            break

    relevant_claims = [
        {
            "claim_id": c.claim_id,
            "claim_type": c.claim_type,
            "statement": c.statement,
        }
        for c in ledger.claims
        if c.status == "VERIFIED" and c.claim_type in _CLAIM_TYPES_FOR_FAQ
    ]

    return {
        "research_gaps": list(ledger.gaps or []),
        "research_question_seeds": seeds,
        "faq_relevant_claims": relevant_claims[:40],
    }
