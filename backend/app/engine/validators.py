"""Deterministic CODE validators and safe auto-fixes."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from app.models.schemas import Claim, ClientRulesPack, FactLedger, PdpDraft, RuleDef, RuleResult

UK_SPELLING: dict[str, str] = {
    "color": "colour", "colors": "colours", "colored": "coloured", "colorful": "colourful",
    "aluminum": "aluminium", "gray": "grey", "tire": "tyre", "tires": "tyres",
    "liter": "litre", "liters": "litres", "center": "centre", "centers": "centres", "centered": "centred",
    "fiber": "fibre", "fibers": "fibres", "behavior": "behaviour", "favorite": "favourite", "labor": "labour",
    "catalog": "catalogue", "mold": "mould", "molded": "moulded", "molding": "moulding",
    "organize": "organise", "organized": "organised", "organizing": "organising", "organizer": "organiser",
    "organization": "organisation", "optimize": "optimise", "optimized": "optimised",
    "minimize": "minimise", "minimized": "minimised", "maximize": "maximise", "maximized": "maximised",
    "customize": "customise", "customized": "customised", "recognize": "recognise", "recognized": "recognised",
    "stabilize": "stabilise", "stabilized": "stabilised", "utilize": "utilise", "utilized": "utilised",
    "realize": "realise", "standardized": "standardised", "analyze": "analyse", "analyzed": "analysed",
    "defense": "defence", "leveling": "levelling", "traveling": "travelling", "traveled": "travelled",
    "canceled": "cancelled", "modeling": "modelling", "fueled": "fuelled", "signaling": "signalling",
    "labeled": "labelled", "labeling": "labelling", "jewelry": "jewellery", "plow": "plough",
    "artifact": "artefact", "gage": "gauge", "gages": "gauges", "maneuver": "manoeuvre",
    "odor": "odour", "vapor": "vapour", "humor": "humour", "harbor": "harbour", "armor": "armour",
    "neighbor": "neighbour", "endeavor": "endeavour", "sulfur": "sulphur", "galvanized": "galvanised",
    "pressurized": "pressurised", "summarize": "summarise", "emphasize": "emphasise",
    "prioritize": "prioritise", "characterized": "characterised",
}
_UK_RE = re.compile(
    r"\b(" + "|".join(sorted(map(re.escape, UK_SPELLING), key=len, reverse=True)) + r")\b",
    re.I,
)
_METER_RE = re.compile(r"(\d)\s?(meter|meters)\b", re.I)
_LINK_RE = re.compile(
    r"https?://\S+|www\.\S+|\[[^\]]+\]\([^)]+\)|\b[\w.-]+\.(?:co\.uk|com|org|net|uk)\b(?:/\S*)?",
    re.I,
)
_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-/.,]*")


def _match_case(src: str, repl: str) -> str:
    if src.isupper():
        return repl.upper()
    if src[0].isupper():
        return repl[0].upper() + repl[1:]
    return repl


def uk_fix_text(text: str) -> tuple[str, list[str]]:
    changes: list[str] = []

    def sub(m: re.Match) -> str:
        repl = _match_case(m.group(0), UK_SPELLING[m.group(0).lower()])
        if repl != m.group(0):
            changes.append(f"{m.group(0)} -> {repl}")
        return repl

    text = _UK_RE.sub(sub, text)

    def meter(m: re.Match) -> str:
        word = "metres" if m.group(2).lower().endswith("s") else "metre"
        changes.append(f"{m.group(2)} -> {word}")
        return m.group(1) + (" " if " " in m.group(0) else "") + word

    text = _METER_RE.sub(meter, text)
    return text, changes


def strip_links(text: str) -> tuple[str, list[str]]:
    hits = _LINK_RE.findall(text)
    if not hits:
        return text, []
    cleaned = _LINK_RE.sub("", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned, [f"removed link-like token: {h}" for h in hits]


def word_count(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))


def draft_to_plaintext(draft: PdpDraft) -> str:
    parts: list[str] = [draft.title or ""]
    for b in draft.overview:
        parts.append(b.text)
    for f in draft.features:
        parts.append(f"{f.feature} {f.benefit}".strip())
    for s in draft.specifications:
        parts.append(f"{s.attribute}: {s.value}")
    for q in draft.faqs:
        parts.append(f"{q.question} {q.answer}")
    for b in draft.site_benefits:
        parts.append(b.text)
    return "\n".join(p for p in parts if p)


def normalise_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def excerpt_supported(excerpt: str, source_text: str) -> bool:
    """True when the excerpt (normalised) appears in the source markdown/html text."""
    ex = normalise_for_match(excerpt)
    src = normalise_for_match(source_text)
    if not ex or len(ex) < 8:
        return False
    return ex in src


def apply_uk_spelling_to_draft(draft: PdpDraft) -> tuple[PdpDraft, list[str]]:
    changes: list[str] = []
    title, c = uk_fix_text(draft.title)
    changes.extend(c)
    draft.title = title
    for b in draft.overview:
        b.text, c = uk_fix_text(b.text)
        changes.extend(c)
    for f in draft.features:
        f.feature, c1 = uk_fix_text(f.feature)
        f.benefit, c2 = uk_fix_text(f.benefit)
        changes.extend(c1 + c2)
    for s in draft.specifications:
        s.attribute, c1 = uk_fix_text(s.attribute)
        s.value, c2 = uk_fix_text(s.value)
        changes.extend(c1 + c2)
    for q in draft.faqs:
        q.question, c1 = uk_fix_text(q.question)
        q.answer, c2 = uk_fix_text(q.answer)
        changes.extend(c1 + c2)
    for b in draft.site_benefits:
        b.text, c = uk_fix_text(b.text)
        changes.extend(c)
    return draft, changes


def apply_link_strip_to_draft(draft: PdpDraft) -> tuple[PdpDraft, list[str]]:
    changes: list[str] = []
    draft.title, c = strip_links(draft.title)
    changes.extend(c)
    for b in draft.overview:
        b.text, c = strip_links(b.text)
        changes.extend(c)
    for f in draft.features:
        f.feature, c1 = strip_links(f.feature)
        f.benefit, c2 = strip_links(f.benefit)
        changes.extend(c1 + c2)
    for s in draft.specifications:
        s.value, c = strip_links(s.value)
        changes.extend(c)
    for q in draft.faqs:
        q.answer, c = strip_links(q.answer)
        changes.extend(c)
    for b in draft.site_benefits:
        b.text, c = strip_links(b.text)
        changes.extend(c)
    return draft, changes


def remove_banned_terms(text: str, banned: Iterable[str]) -> tuple[str, list[str]]:
    changes: list[str] = []
    out = text
    for term in sorted(banned, key=len, reverse=True):
        pattern = re.compile(re.escape(term), re.I)
        if pattern.search(out):
            out = pattern.sub("", out)
            changes.append(f"removed banned term: {term}")
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out, changes


def apply_banned_terms_to_draft(draft: PdpDraft, banned: list[str]) -> tuple[PdpDraft, list[str]]:
    changes: list[str] = []
    draft.title, c = remove_banned_terms(draft.title, banned)
    changes.extend(c)
    for b in draft.overview:
        b.text, c = remove_banned_terms(b.text, banned)
        changes.extend(c)
    for f in draft.features:
        f.feature, c1 = remove_banned_terms(f.feature, banned)
        f.benefit, c2 = remove_banned_terms(f.benefit, banned)
        changes.extend(c1 + c2)
    for q in draft.faqs:
        q.answer, c = remove_banned_terms(q.answer, banned)
        changes.extend(c)
    for b in draft.site_benefits:
        b.text, c = remove_banned_terms(b.text, banned)
        changes.extend(c)
    return draft, changes


@dataclass
class ValidationContext:
    draft: PdpDraft | None = None
    ledger: FactLedger | None = None
    source_texts: dict[int, str] = field(default_factory=dict)
    competitor_names: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)


@dataclass
class ValidationOutcome:
    results: list[RuleResult]
    draft: PdpDraft | None
    auto_fixes: list[str] = field(default_factory=list)


def _rule_map(pack: ClientRulesPack) -> dict[str, RuleDef]:
    return {r.rule_id: r for r in pack.rules}


def run_code_validators(
    pack: ClientRulesPack,
    ctx: ValidationContext,
    *,
    stage: str = "qc",
    apply_fixes: bool = True,
) -> ValidationOutcome:
    """Evaluate CODE/HYBRID rules that have deterministic implementations."""
    results: list[RuleResult] = []
    auto_fixes: list[str] = []
    draft = ctx.draft
    rules = [r for r in pack.rules if stage in r.scope and r.validation_method in ("CODE", "HYBRID")]

    # ACC-003 excerpt verification
    if any(r.rule_id == "ACC-003" for r in rules) and ctx.ledger:
        bad: list[str] = []
        for claim in ctx.ledger.claims:
            if claim.status != "VERIFIED":
                continue
            for ev in claim.evidence:
                src = ctx.source_texts.get(ev.source_id, "")
                if not excerpt_supported(ev.excerpt, src):
                    bad.append(claim.claim_id)
                    break
        results.append(
            RuleResult(
                rule_id="ACC-003",
                description=_rule_map(pack)["ACC-003"].description,
                status="PASS" if not bad else "FAIL",
                evidence="all excerpts matched" if not bad else f"unsupported excerpts on claims: {', '.join(bad)}",
            )
        )

    if draft is None:
        return ValidationOutcome(results=results, draft=None, auto_fixes=auto_fixes)

    # STY-001 UK spelling
    if any(r.rule_id == "STY-001" for r in rules):
        text = draft_to_plaintext(draft)
        _, detected = uk_fix_text(text)
        if detected and apply_fixes:
            draft, changes = apply_uk_spelling_to_draft(draft)
            auto_fixes.extend(changes)
            results.append(
                RuleResult(
                    rule_id="STY-001",
                    description=_rule_map(pack)["STY-001"].description,
                    status="PASS",
                    evidence=f"auto-corrected {len(changes)} spelling(s)",
                    auto_fixed=True,
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_id="STY-001",
                    description=_rule_map(pack)["STY-001"].description,
                    status="PASS" if not detected else "FAIL",
                    evidence="UK spelling OK" if not detected else f"US spellings: {', '.join(detected[:8])}",
                )
            )

    # STY-002 banned terms
    if any(r.rule_id == "STY-002" for r in rules):
        banned = list(_rule_map(pack)["STY-002"].params.get("banned_terms") or [])
        text = draft_to_plaintext(draft)
        found = [t for t in banned if re.search(re.escape(t), text, re.I)]
        if found and apply_fixes:
            draft, changes = apply_banned_terms_to_draft(draft, found)
            auto_fixes.extend(changes)
            results.append(
                RuleResult(
                    rule_id="STY-002",
                    description=_rule_map(pack)["STY-002"].description,
                    status="PASS",
                    evidence=f"removed: {', '.join(found)}",
                    auto_fixed=True,
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_id="STY-002",
                    description=_rule_map(pack)["STY-002"].description,
                    status="PASS" if not found else "FAIL",
                    evidence="no banned terms" if not found else f"found: {', '.join(found)}",
                )
            )

    # STY-003 links / competitor names
    if any(r.rule_id == "STY-003" for r in rules):
        text = draft_to_plaintext(draft)
        links = _LINK_RE.findall(text)
        comps = [n for n in ctx.competitor_names if n and re.search(rf"\b{re.escape(n)}\b", text, re.I)]
        if links and apply_fixes:
            draft, changes = apply_link_strip_to_draft(draft)
            auto_fixes.extend(changes)
            links = []
        status = "PASS" if not links and not comps else "FAIL"
        evidence_parts = []
        if not links and not comps:
            evidence_parts.append("no links or competitor names")
        if links:
            evidence_parts.append(f"links: {links[:3]}")
        if comps:
            evidence_parts.append(f"competitors mentioned: {comps}")
        results.append(
            RuleResult(
                rule_id="STY-003",
                description=_rule_map(pack)["STY-003"].description,
                status=status,
                evidence="; ".join(evidence_parts),
                auto_fixed=bool(apply_fixes and (links or False)),
            )
        )

    # SEO-001 title length
    if any(r.rule_id == "SEO-001" for r in rules):
        max_chars = int(_rule_map(pack)["SEO-001"].params.get("title_max_chars") or 150)
        length = len(draft.title or "")
        results.append(
            RuleResult(
                rule_id="SEO-001",
                description=_rule_map(pack)["SEO-001"].description,
                status="PASS" if length <= max_chars else "FAIL",
                evidence=f"title length {length}/{max_chars}",
            )
        )

    # SEO-002 word count
    if any(r.rule_id == "SEO-002" for r in rules):
        max_words = int(_rule_map(pack)["SEO-002"].params.get("max_words") or 1500)
        wc = word_count(draft_to_plaintext(draft))
        draft.word_count = wc
        results.append(
            RuleResult(
                rule_id="SEO-002",
                description=_rule_map(pack)["SEO-002"].description,
                status="PASS" if wc <= max_words else "FAIL",
                evidence=f"word count {wc}/{max_words}",
            )
        )

    # FMT-001 structure
    if any(r.rule_id == "FMT-001" for r in rules):
        missing = []
        if not (draft.title or "").strip():
            missing.append("title")
        if not draft.overview:
            missing.append("overview")
        if not draft.features:
            missing.append("features")
        if not draft.specifications:
            missing.append("specifications")
        results.append(
            RuleResult(
                rule_id="FMT-001",
                description=_rule_map(pack)["FMT-001"].description,
                status="PASS" if not missing else "FAIL",
                evidence="structure complete" if not missing else f"missing: {', '.join(missing)}",
            )
        )

    # ACC-002 claim citations on body blocks (hybrid, code side)
    if any(r.rule_id == "ACC-002" for r in rules):
        verified_ids = {c.claim_id for c in (ctx.ledger.claims if ctx.ledger else []) if c.status == "VERIFIED"}
        uncited = 0
        for b in draft.overview:
            if b.text.strip() and not any(cid in verified_ids for cid in b.claim_ids):
                uncited += 1
        for f in draft.features:
            if (f.feature or f.benefit).strip() and not any(cid in verified_ids for cid in f.claim_ids):
                uncited += 1
        for s in draft.specifications:
            if s.value.strip() and not any(cid in verified_ids for cid in s.claim_ids):
                uncited += 1
        results.append(
            RuleResult(
                rule_id="ACC-002",
                description=_rule_map(pack)["ACC-002"].description,
                status="PASS" if uncited == 0 else "FAIL",
                evidence="all blocks cite verified claims" if uncited == 0 else f"{uncited} block(s) lack verified claim_ids",
            )
        )

    # GEO-001 gaps addressed (preferred / flag)
    if any(r.rule_id == "GEO-001" for r in rules):
        gaps = ctx.gaps or (ctx.ledger.gaps if ctx.ledger else [])
        if not gaps:
            results.append(
                RuleResult(
                    rule_id="GEO-001",
                    description=_rule_map(pack)["GEO-001"].description,
                    status="SKIP",
                    evidence="no verified gaps in ledger",
                )
            )
        else:
            addressed = set(draft.gaps_addressed or [])
            missing = [g for g in gaps if g not in addressed]
            results.append(
                RuleResult(
                    rule_id="GEO-001",
                    description=_rule_map(pack)["GEO-001"].description,
                    status="PASS" if not missing else "FLAG",
                    evidence="all gaps addressed" if not missing else f"unaddressed: {missing[:5]}",
                )
            )

    return ValidationOutcome(results=results, draft=draft, auto_fixes=auto_fixes)


def enforce_fact_excerpts(ledger: FactLedger, source_texts: dict[int, str]) -> FactLedger:
    """Mark claims EXCLUDED when evidence excerpts are not in source text."""
    notes: list[str] = []
    verified = 0
    excluded = 0
    for claim in ledger.claims:
        if claim.status != "VERIFIED":
            excluded += 1
            continue
        if not claim.evidence:
            claim.status = "EXCLUDED"
            claim.exclusion_reason = "no evidence"
            excluded += 1
            notes.append(f"{claim.claim_id}: no evidence")
            continue
        ok = all(excerpt_supported(ev.excerpt, source_texts.get(ev.source_id, "")) for ev in claim.evidence)
        if not ok:
            claim.status = "EXCLUDED"
            claim.exclusion_reason = "excerpt not found in source"
            excluded += 1
            notes.append(f"{claim.claim_id}: excerpt mismatch")
        else:
            verified += 1
    ledger.verified_count = verified
    ledger.excluded_count = excluded
    ledger.enforcement_notes = notes
    return ledger


def domain_is_untrusted(domain: str, untrusted: Iterable[str]) -> bool:
    d = (domain or "").lower().removeprefix("www.")
    for u in untrusted:
        u = u.lower().removeprefix("www.")
        if d == u or d.endswith("." + u):
            return True
    return False
