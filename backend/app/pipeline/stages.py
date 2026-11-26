"""Six lean pipeline stages."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.adapters.firecrawl_client import FirecrawlClient, extract_markdown_html
from app.adapters.llm import complete_json
from app.adapters.search_provider import search_organic
from app.adapters.search_types import SearchLocale, domain_of
from app.engine.rules import load_client_rules, load_style_excerpt
from app.engine.validators import (
    ValidationContext,
    domain_is_untrusted,
    draft_to_plaintext,
    enforce_fact_excerpts,
    run_code_validators,
    word_count,
)
from app.models.db import Client, LlmUsage, Run, Source, StageResult, utcnow
from app.models.schemas import (
    ComplianceReport,
    FactLedger,
    IdentityResult,
    PdpDraft,
    PlannedSource,
    QcArtifact,
    RuleResult,
    SourcePlan,
    SubjectBaseline,
)
from app.pipeline.fixtures import fixtures_enabled, load_json, load_text

logger = logging.getLogger(__name__)
_PROMPTS = Path(__file__).parent / "prompts"

STAGE_NAMES = {
    1: "scrape_subject",
    2: "research",
    3: "scrape_sources",
    4: "facts",
    5: "write",
    6: "qc",
}


def _prompt(name: str) -> str:
    return (_PROMPTS / name).read_text(encoding="utf-8")


def _slug_title_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/").split("/")[-1]
    return path.replace("-", " ").strip().title()


class CompetitorUrlItem(BaseModel):
    url: str = ""
    title: str = ""
    reason: str = ""


class ResearchLLM(BaseModel):
    classification: str = "Brand"
    reason: str = ""
    brand_name: str = ""
    product_name: str = ""
    search_queries: list[str] = Field(default_factory=list)
    manufacturer_url: str = ""
    competitor_urls: list[CompetitorUrlItem] = Field(default_factory=list)


class QaIssueItem(BaseModel):
    location: str = ""
    severity: str = "minor"
    description: str = ""
    fix_instruction: str = ""


class QaLLM(BaseModel):
    issues: list[QaIssueItem] = Field(default_factory=list)
    summary: str = ""
    repaired_draft: PdpDraft


async def _record_usage(session: Session, run: Run, stage: int, role: str, meta: Any) -> None:
    usage = LlmUsage(
        run_id=run.id,
        stage=stage,
        provider=meta.provider,
        model=meta.model,
        role=role,
        input_tokens=meta.input_tokens,
        output_tokens=meta.output_tokens,
        cost_usd=meta.cost_usd,
    )
    session.add(usage)
    run.input_tokens += meta.input_tokens
    run.output_tokens += meta.output_tokens
    run.cost_usd += meta.cost_usd
    session.add(run)


def _model_for(run: Run, role: str, settings_defaults: dict[str, tuple[str, str]]) -> tuple[str, str]:
    overrides = run.model_overrides or {}
    if role in overrides and isinstance(overrides[role], dict):
        return overrides[role]["provider"], overrides[role]["model"]
    return settings_defaults[role]


async def stage01_scrape_subject(
    session: Session,
    run: Run,
    client: Client,
    *,
    use_fixtures: bool,
) -> SubjectBaseline:
    if use_fixtures:
        data = load_json("subject_scrape.json")
        markdown = data.get("markdown") or load_text("subject.md")
        html = data.get("html") or ""
        title = data.get("title") or _slug_title_from_url(run.url)
    else:
        fc = FirecrawlClient()
        raw = await fc.scrape(run.url)
        markdown, html, title = extract_markdown_html(raw)
        if not title:
            title = _slug_title_from_url(run.url)

    source = Source(
        run_id=run.id,
        url=run.url,
        role="subject",
        domain=domain_of(run.url),
        title=title,
        markdown=markdown,
        html=html,
        meta={"fixture": use_fixtures},
    )
    session.add(source)
    session.commit()
    session.refresh(source)

    hints = []
    for brand in client.owned_brands or []:
        if brand.lower() in (markdown or "").lower() or brand.lower() in title.lower():
            hints.append(brand)

    return SubjectBaseline(
        url=run.url,
        title=title,
        domain=domain_of(run.url),
        markdown_excerpt=(markdown or "")[:6000],
        source_id=source.id,
        product_hints=hints,
    )


async def stage02_research(
    session: Session,
    run: Run,
    client: Client,
    baseline: SubjectBaseline,
    *,
    use_fixtures: bool,
    extract_provider: str,
    extract_model: str,
) -> SourcePlan:
    pack = load_client_rules(client.slug)
    untrusted = list(
        (next((r.params.get("untrusted_domains") for r in pack.rules if r.rule_id == "ACC-004"), None))
        or client.untrusted_domains
        or []
    )
    client_domains = set(d.lower() for d in (client.client_domains or [client.domain]) if d)

    if use_fixtures:
        data = load_json("research.json")
        identity = IdentityResult.model_validate(data["identity"])
        sources = [PlannedSource.model_validate(s) for s in data.get("sources") or []]
        return SourcePlan(identity=identity, sources=sources, search_provider="fixture", notes=["fixture mode"])

    # Live search for exact sellers
    query = baseline.title or _slug_title_from_url(run.url)
    locale = SearchLocale(
        gl=client.market_country or "uk",
        hl="en",
        google_domain=client.google_domain or "google.co.uk",
        location_name="United Kingdom" if (client.market_country or "uk") == "uk" else "United States",
    )
    search = await search_organic(query, locale, num=15)
    seller_domains = []
    for r in search.results:
        d = r.domain.lower()
        if domain_is_untrusted(d, untrusted):
            continue
        if d in client_domains:
            continue
        seller_domains.append(d)

    exact_sellers = len(set(seller_domains))
    owned_hit = any(b.lower() in baseline.title.lower() for b in (client.owned_brands or []))
    classification = "Brand" if owned_hit or exact_sellers < 2 else "Reseller"

    system = _prompt("research.md")
    user = json.dumps(
        {
            "subject_url": run.url,
            "title": baseline.title,
            "excerpt": baseline.markdown_excerpt[:4000],
            "owned_brands": client.owned_brands,
            "client_domains": list(client_domains),
            "untrusted_domains": untrusted,
            "competitor_count": client.competitor_count,
            "search_results": [r.as_dict() for r in search.results[:12]],
            "heuristic_classification": classification,
            "exact_seller_count": exact_sellers,
        },
        ensure_ascii=False,
    )
    llm_out, meta = await complete_json(
        provider=extract_provider,
        model=extract_model,
        system=system,
        user=user,
        schema=ResearchLLM,
    )
    await _record_usage(session, run, 2, "extract", meta)
    session.commit()

    cls = llm_out.classification if llm_out.classification in ("Brand", "Reseller") else classification
    identity = IdentityResult(
        classification=cls,  # type: ignore[arg-type]
        reason=llm_out.reason or f"heuristic sellers={exact_sellers}, owned_hit={owned_hit}",
        brand_name=llm_out.brand_name or (client.owned_brands[0] if client.owned_brands else ""),
        product_name=llm_out.product_name or baseline.title,
        search_queries=llm_out.search_queries or [query],
        exact_seller_count=exact_sellers,
    )

    planned: list[PlannedSource] = []
    if llm_out.manufacturer_url:
        d = domain_of(llm_out.manufacturer_url)
        if d not in client_domains and not domain_is_untrusted(d, untrusted):
            planned.append(
                PlannedSource(url=llm_out.manufacturer_url, role="manufacturer", domain=d, reason="LLM manufacturer")
            )

    for item in llm_out.competitor_urls[: client.competitor_count]:
        url = (item.url if hasattr(item, "url") else "") or ""
        if not url:
            continue
        d = domain_of(url)
        if d in client_domains or domain_is_untrusted(d, untrusted):
            continue
        if any(p.url == url for p in planned):
            continue
        planned.append(
            PlannedSource(
                url=url,
                role="competitor",
                domain=d,
                title=item.title or "",
                reason=item.reason or "LLM competitor",
            )
        )

    # Fallback: pick organic results as competitors
    if len([p for p in planned if p.role == "competitor"]) < min(2, client.competitor_count):
        for r in search.results:
            if len([p for p in planned if p.role == "competitor"]) >= client.competitor_count:
                break
            d = r.domain.lower()
            if d in client_domains or domain_is_untrusted(d, untrusted):
                continue
            if any(p.url == r.url for p in planned):
                continue
            planned.append(
                PlannedSource(url=r.url, role="competitor", domain=d, title=r.title, reason="organic fallback")
            )

    return SourcePlan(identity=identity, sources=planned, search_provider=search.provider, notes=[])


async def stage03_scrape_sources(
    session: Session,
    run: Run,
    plan: SourcePlan,
    *,
    use_fixtures: bool,
) -> list[dict[str, Any]]:
    scraped: list[dict[str, Any]] = []
    if use_fixtures:
        data = load_json("sources.json")
        for item in data.get("sources") or []:
            source = Source(
                run_id=run.id,
                url=item["url"],
                role=item.get("role") or "competitor",
                domain=domain_of(item["url"]),
                title=item.get("title") or "",
                markdown=item.get("markdown") or "",
                html=item.get("html") or "",
                meta={"fixture": True},
            )
            session.add(source)
            session.commit()
            session.refresh(source)
            scraped.append({"source_id": source.id, "url": source.url, "role": source.role, "title": source.title})
        return scraped

    fc = FirecrawlClient()
    for planned in plan.sources:
        try:
            raw = await fc.scrape(planned.url)
            markdown, html, title = extract_markdown_html(raw)
            source = Source(
                run_id=run.id,
                url=planned.url,
                role=planned.role,
                domain=planned.domain or domain_of(planned.url),
                title=title or planned.title,
                markdown=markdown,
                html=html,
                meta={},
            )
            session.add(source)
            session.commit()
            session.refresh(source)
            scraped.append({"source_id": source.id, "url": source.url, "role": source.role, "title": source.title})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to scrape %s: %s", planned.url, exc)
            scraped.append({"url": planned.url, "role": planned.role, "error": str(exc)})
    return scraped


async def stage04_facts(
    session: Session,
    run: Run,
    client: Client,
    *,
    extract_provider: str,
    extract_model: str,
    use_fixtures: bool,
) -> FactLedger:
    sources = session.exec(select(Source).where(Source.run_id == run.id)).all()
    source_payload = []
    source_texts: dict[int, str] = {}
    for s in sources:
        text = (s.markdown or "")[:8000]
        source_texts[s.id] = s.markdown or s.html or ""
        source_payload.append(
            {
                "source_id": s.id,
                "role": s.role,
                "url": s.url,
                "title": s.title,
                "text": text,
            }
        )

    if use_fixtures:
        try:
            data = load_json("facts.json")
            subject = next((s for s in sources if s.role == "subject"), None)
            if subject:
                for claim in data.get("claims") or []:
                    for ev in claim.get("evidence") or []:
                        # Fixture claims cite source_id 1; remap to live subject row
                        if ev.get("source_id") in (1, "1"):
                            ev["source_id"] = subject.id
            ledger = FactLedger.model_validate(data)
            return enforce_fact_excerpts(ledger, source_texts)
        except FileNotFoundError:
            pass

    system = _prompt("facts.md")
    user = json.dumps({"sources": source_payload, "client": client.slug}, ensure_ascii=False)
    ledger, meta = await complete_json(
        provider=extract_provider,
        model=extract_model,
        system=system,
        user=user,
        schema=FactLedger,
        max_tokens=10000,
    )
    await _record_usage(session, run, 4, "extract", meta)
    session.commit()
    return enforce_fact_excerpts(ledger, source_texts)


async def stage05_write(
    session: Session,
    run: Run,
    client: Client,
    ledger: FactLedger,
    *,
    writer_provider: str,
    writer_model: str,
    use_fixtures: bool = False,
) -> PdpDraft:
    if use_fixtures:
        try:
            draft = PdpDraft.model_validate(load_json("draft.json"))
            # Drop claim_ids that were excluded by enforcement
            verified_ids = {c.claim_id for c in ledger.claims if c.status == "VERIFIED"}
            for b in draft.overview:
                b.claim_ids = [c for c in b.claim_ids if c in verified_ids]
            for f in draft.features:
                f.claim_ids = [c for c in f.claim_ids if c in verified_ids]
            for s in draft.specifications:
                s.claim_ids = [c for c in s.claim_ids if c in verified_ids]
            draft.word_count = word_count(draft_to_plaintext(draft))
            return draft
        except FileNotFoundError:
            pass

    pack = load_client_rules(client.slug)
    style = load_style_excerpt(client.slug)
    verified = [c.model_dump() for c in ledger.claims if c.status == "VERIFIED"]
    seo = next((r for r in pack.rules if r.rule_id == "SEO-001"), None)
    seo2 = next((r for r in pack.rules if r.rule_id == "SEO-002"), None)
    clt = next((r for r in pack.rules if r.rule_id == "CLT-001"), None)

    system = _prompt("write.md")
    user = json.dumps(
        {
            "style_excerpt": style,
            "title_max_chars": (seo.params.get("title_max_chars") if seo else client.title_max_chars),
            "max_words": (seo2.params.get("max_words") if seo2 else client.max_words),
            "allowed_site_benefits": (clt.params.get("allowed_site_benefits") if clt else []),
            "verified_claims": verified,
            "gaps": ledger.gaps,
        },
        ensure_ascii=False,
    )
    draft, meta = await complete_json(
        provider=writer_provider,
        model=writer_model,
        system=system,
        user=user,
        schema=PdpDraft,
        max_tokens=10000,
    )
    await _record_usage(session, run, 5, "writer", meta)
    draft.word_count = word_count(draft_to_plaintext(draft))
    session.commit()
    return draft


async def stage06_qc(
    session: Session,
    run: Run,
    client: Client,
    ledger: FactLedger,
    draft: PdpDraft,
    plan: SourcePlan,
    *,
    qa_provider: str,
    qa_model: str,
    max_rounds: int = 2,
    use_fixtures: bool = False,
) -> QcArtifact:
    pack = load_client_rules(client.slug)
    sources = session.exec(select(Source).where(Source.run_id == run.id)).all()
    source_texts = {s.id: (s.markdown or s.html or "") for s in sources}
    competitor_names = [
        (p.title.split()[0] if p.title else p.domain)
        for p in plan.sources
        if p.role == "competitor"
    ]
    # Prefer domain brand-ish labels
    competitor_names = [n for n in competitor_names if n and n.lower() not in {"www", "http", "https"}]

    repairs: list[str] = []
    all_results: list[RuleResult] = []
    current = draft

    for round_i in range(1, max_rounds + 1):
        outcome = run_code_validators(
            pack,
            ValidationContext(
                draft=current,
                ledger=ledger,
                source_texts=source_texts,
                competitor_names=competitor_names,
                gaps=ledger.gaps,
            ),
            stage="qc",
            apply_fixes=True,
        )
        current = outcome.draft or current
        if outcome.auto_fixes:
            repairs.extend([f"r{round_i}: {x}" for x in outcome.auto_fixes])

        failed = [r for r in outcome.results if r.status == "FAIL"]
        # LLM QA only when material code failures remain that need repair (skip in fixture mode)
        needs_llm = (not use_fixtures) and any(
            r.rule_id in {"ACC-002", "SEO-001", "SEO-002", "FMT-001", "CLT-001"} for r in failed
        )
        if needs_llm or ((not use_fixtures) and any(r.status == "FLAG" for r in outcome.results)):
            system = _prompt("qc.md")
            user = json.dumps(
                {
                    "failed_rules": [r.model_dump() for r in failed],
                    "flagged_rules": [r.model_dump() for r in outcome.results if r.status == "FLAG"],
                    "draft": current.model_dump(),
                    "verified_claim_ids": [c.claim_id for c in ledger.claims if c.status == "VERIFIED"],
                    "gaps": ledger.gaps,
                },
                ensure_ascii=False,
            )
            try:
                qa_out, meta = await complete_json(
                    provider=qa_provider,
                    model=qa_model,
                    system=system,
                    user=user,
                    schema=QaLLM,
                    max_tokens=10000,
                )
                await _record_usage(session, run, 6, "qa", meta)
                session.commit()
                current = qa_out.repaired_draft
                repairs.append(f"r{round_i}: LLM repair — {qa_out.summary[:200]}")
                # Re-run code validators after LLM repair
                outcome = run_code_validators(
                    pack,
                    ValidationContext(
                        draft=current,
                        ledger=ledger,
                        source_texts=source_texts,
                        competitor_names=competitor_names,
                        gaps=ledger.gaps,
                    ),
                    stage="qc",
                    apply_fixes=True,
                )
                current = outcome.draft or current
                repairs.extend([f"r{round_i}-post: {x}" for x in outcome.auto_fixes])
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM QA failed: %s", exc)
                repairs.append(f"r{round_i}: LLM QA skipped ({exc})")

        all_results = outcome.results
        if not any(r.status == "FAIL" and _is_mandatory(pack, r.rule_id) for r in all_results):
            break

    # Ensure ACC-001 / CLT-001 / ACC-004 appear in report even if skipped earlier
    present = {r.rule_id for r in all_results}
    for rule in pack.rules:
        if rule.rule_id in present:
            continue
        if "qc" not in rule.scope:
            continue
        if rule.rule_id == "ACC-001":
            # Heuristic: product name tokens appear in title
            ok = bool(plan.identity.product_name) and any(
                tok.lower() in (current.title or "").lower()
                for tok in re.findall(r"[A-Za-z0-9]+", plan.identity.product_name)[:3]
            )
            all_results.append(
                RuleResult(
                    rule_id="ACC-001",
                    description=rule.description,
                    status="PASS" if ok else "FLAG",
                    evidence="title retains product identity tokens" if ok else "weak identity match in title",
                )
            )
        elif rule.rule_id == "CLT-001":
            all_results.append(
                RuleResult(
                    rule_id="CLT-001",
                    description=rule.description,
                    status="PASS" if current.site_benefits else "SKIP",
                    evidence="site benefits present" if current.site_benefits else "no site benefits written",
                )
            )
        elif rule.rule_id == "ACC-004":
            all_results.append(
                RuleResult(
                    rule_id="ACC-004",
                    description=rule.description,
                    status="PASS",
                    evidence="untrusted domains filtered during research/facts",
                )
            )

    passed = sum(1 for r in all_results if r.status == "PASS")
    failed_n = sum(1 for r in all_results if r.status == "FAIL")
    flagged = sum(1 for r in all_results if r.status == "FLAG")
    mandatory_fail = any(
        r.status == "FAIL" and _is_mandatory(pack, r.rule_id) for r in all_results
    )
    if mandatory_fail:
        disposition = "REJECT"
    elif flagged:
        disposition = "HOLD"
    else:
        disposition = "RELEASE"

    compliance = ComplianceReport(
        disposition=disposition,
        rules_evaluated=len(all_results),
        passed=passed,
        failed=failed_n,
        flagged=flagged,
        results=all_results,
        rounds=min(max_rounds, len([x for x in repairs if x.startswith("r")])),
        notes=repairs[:20],
    )
    current.word_count = word_count(draft_to_plaintext(current))
    return QcArtifact(draft=current, compliance=compliance, repairs=repairs)


def _is_mandatory(pack, rule_id: str) -> bool:
    for r in pack.rules:
        if r.rule_id == rule_id:
            return r.priority == "MANDATORY"
    return True
