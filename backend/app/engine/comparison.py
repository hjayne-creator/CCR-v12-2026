"""Comparison-table suitability helpers (CMP-001)."""
from __future__ import annotations

import re
from typing import Any, Iterable

from app.models.schemas import Claim, ComparisonTable, FactLedger, PdpDraft

# Canonical purchase-decision dimensions → match tokens in claims / titles
DEFAULT_DIMENSION_TOKENS: dict[str, tuple[str, ...]] = {
    "capacity": ("capacity", "tonne", "ton", "load", "rating"),
    "dimensions": ("dimension", "size", "length", "width", "depth", "height", "mm", "cm"),
    "min_height": ("minimum height", "min height", "minimum lift", "closed height"),
    "max_height": ("maximum height", "max height", "maximum lift", "lift height"),
    "material": ("material", "steel", "aluminium", "aluminum", "alloy"),
    "electrical_rating": ("voltage", "vdc", "vac", "amp", "watt", "hz", "electrical"),
    "mounting": ("mount", "mounting", "bracket", "fix fitting"),
    "compatibility": ("compatible", "compatibility", "fits", "suitable for"),
    "warranty": ("warranty", "guarantee"),
    "included_components": ("includes", "included", "package", "contents", "kit"),
    "weight": ("weight", "kg", "lb"),
    "wheels": ("wheel", "castor", "caster"),
    "safety": ("safety", "overload", "valve", "ce marked"),
}

_BRAND_STOP = {
    "the", "and", "for", "with", "low", "high", "new", "pro", "set", "kit",
    "uk", "ltd", "limited", "official", "buy",
}


def normalize_label_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def brand_model_label(title: str, *, brand_hints: Iterable[str] | None = None) -> str:
    """Prefer a short brand + model style label from a long PDP title."""
    title = normalize_label_text(title)
    if not title:
        return "Product"
    hints = [h for h in (brand_hints or []) if h]
    brand = ""
    for h in sorted(hints, key=len, reverse=True):
        if re.search(rf"\b{re.escape(h)}\b", title, re.I):
            brand = h
            break
    # Keep first ~8 meaningful tokens; drop trailing SEO fluff after common separators
    core = re.split(r"\s[|–—-]\s|\s+\|\s+", title)[0]
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’./-]*", core)
    kept: list[str] = []
    for tok in tokens:
        low = tok.lower()
        if low in _BRAND_STOP and len(kept) >= 2:
            continue
        kept.append(tok)
        if len(kept) >= 8:
            break
    label = " ".join(kept) if kept else title
    if brand and brand.lower() not in label.lower():
        label = f"{brand} {label}"
    return normalize_label_text(label)[:80]


def extract_spec_keys(
    texts: Iterable[str],
    *,
    dimension_tokens: dict[str, tuple[str, ...]] | None = None,
) -> set[str]:
    """Map free text / claim statements onto canonical dimension keys."""
    dims = dimension_tokens or DEFAULT_DIMENSION_TOKENS
    blob = " ".join(t for t in texts if t).lower()
    if not blob:
        return set()
    found: set[str] = set()
    for key, tokens in dims.items():
        if any(tok in blob for tok in tokens):
            found.add(key)
    return found


def claim_texts_for_source(ledger: FactLedger, source_id: int) -> list[str]:
    texts: list[str] = []
    for claim in ledger.claims:
        if claim.status != "VERIFIED":
            continue
        if any(ev.source_id == source_id for ev in claim.evidence):
            texts.append(claim.statement)
            for ev in claim.evidence:
                if ev.source_id == source_id:
                    texts.append(ev.excerpt)
    return texts


def build_dimension_token_map(attribute_examples: list[str] | None) -> dict[str, tuple[str, ...]]:
    dims = dict(DEFAULT_DIMENSION_TOKENS)
    for ex in attribute_examples or []:
        key = re.sub(r"[^a-z0-9]+", "_", ex.lower()).strip("_")
        if not key:
            continue
        tokens = tuple({key.replace("_", " "), *(w for w in key.split("_") if len(w) > 2)})
        dims[key] = tokens
    return dims


def suitable_alternatives(
    *,
    ledger: FactLedger,
    alternatives: list[dict[str, Any]],
    subject_source_id: int | None,
    min_overlap: int = 2,
    attribute_examples: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Keep alternatives that share enough verified spec dimensions with the subject."""
    dims = build_dimension_token_map(attribute_examples)
    subject_texts: list[str] = []
    if subject_source_id is not None:
        subject_texts = claim_texts_for_source(ledger, subject_source_id)
    # Fallback: all verified subject-leaning claims if subject id unknown
    if not subject_texts:
        subject_texts = [c.statement for c in ledger.claims if c.status == "VERIFIED"]
    subject_keys = extract_spec_keys(subject_texts, dimension_tokens=dims)

    suitable: list[dict[str, Any]] = []
    for alt in alternatives:
        sid = alt.get("source_id")
        texts = claim_texts_for_source(ledger, int(sid)) if sid is not None else []
        if not texts:
            # No verified claims from this source → not suitable
            continue
        alt_keys = extract_spec_keys(texts, dimension_tokens=dims)
        overlap = subject_keys & alt_keys
        if len(overlap) >= min_overlap:
            enriched = dict(alt)
            enriched["overlap_keys"] = sorted(overlap)
            enriched["overlap_count"] = len(overlap)
            suitable.append(enriched)
    return suitable


def drop_incomplete_comparison_rows(table: ComparisonTable | None) -> tuple[ComparisonTable | None, int]:
    """Remove rows with any blank cell. Returns (table_or_none, dropped_count)."""
    if table is None:
        return None, 0
    width = len(table.columns or [])
    kept = []
    dropped = 0
    for row in table.rows or []:
        values = list(row.values or [])
        if len(values) != width or any(not (v or "").strip() for v in values):
            dropped += 1
            continue
        kept.append(row)
    if not kept:
        return None, dropped + (0 if table.rows else 0)
    table.rows = kept
    return table, dropped


def finalize_comparison_draft(
    draft: PdpDraft,
    *,
    eligible: bool,
    drop_incomplete_rows: bool = True,
) -> list[str]:
    """Apply eligibility + incomplete-row policy. Returns auto-fix notes."""
    notes: list[str] = []
    if not eligible:
        if draft.comparison is not None:
            draft.comparison = None
            notes.append("CMP-001: omitted comparison (insufficient suitable alternatives)")
        return notes
    if draft.comparison is None:
        return notes
    if drop_incomplete_rows:
        cleaned, dropped = drop_incomplete_comparison_rows(draft.comparison)
        draft.comparison = cleaned
        if dropped:
            notes.append(f"CMP-001: dropped {dropped} incomplete comparison row(s)")
        if cleaned is None:
            notes.append("CMP-001: comparison cleared after dropping incomplete rows")
    return notes
