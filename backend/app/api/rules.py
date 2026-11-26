from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlmodel import Session, select

from app.engine.rules import (
    load_client_rules,
    load_style_excerpt,
    save_client_rules,
    save_style_excerpt,
)
from app.models.db import Client, get_engine
from app.models.schemas import ClientRulesPack
from app.seed import seed_sgs

router = APIRouter(prefix="/api", tags=["rules"])

SCOPE_OPTIONS = ["scrape_subject", "research", "scrape_sources", "facts", "write", "qc"]
PRIORITY_OPTIONS = ["MANDATORY", "PREFERRED"]
VALIDATION_OPTIONS = ["CODE", "LLM", "HYBRID"]
ON_FAILURE_OPTIONS = ["AUTO_CORRECT", "TARGETED_REPAIR", "FLAG", "FAIL"]


class StyleExcerptUpdate(BaseModel):
    text: str = ""


class RulesMeta(BaseModel):
    scope_options: list[str] = Field(default_factory=lambda: SCOPE_OPTIONS)
    priority_options: list[str] = Field(default_factory=lambda: PRIORITY_OPTIONS)
    validation_options: list[str] = Field(default_factory=lambda: VALIDATION_OPTIONS)
    on_failure_options: list[str] = Field(default_factory=lambda: ON_FAILURE_OPTIONS)
    prefix_legend: dict[str, str] = Field(
        default_factory=lambda: {
            "ACC": "Accuracy — identity, claims, evidence, trusted sources",
            "STY": "Style — spelling, banned terms, links / competitor names",
            "SEO": "SEO — title length, word count, title structure",
            "FMT": "Format — required output structure",
            "FAQ": "FAQs — 3–6 research-derived questions",
            "CMP": "Comparison — How it compares table (conditional)",
            "GEO": "Gap / GEO — competitive content gaps",
            "CLT": "Client — client-specific policy",
        }
    )


@router.get("/rules/meta", response_model=RulesMeta)
def rules_meta() -> RulesMeta:
    return RulesMeta()


@router.get("/clients/{slug}/rules")
def get_rules(slug: str) -> dict[str, Any]:
    seed_sgs()
    try:
        pack = load_client_rules(slug)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {
        "pack": pack.model_dump(mode="json"),
        "style_excerpt": load_style_excerpt(slug),
        "meta": RulesMeta().model_dump(),
    }


@router.put("/clients/{slug}/rules")
def put_rules(slug: str, body: dict[str, Any]) -> dict[str, Any]:
    seed_sgs()
    # Accept either raw pack or { pack: {...} }
    payload = body.get("pack") if isinstance(body.get("pack"), dict) else body
    try:
        pack = ClientRulesPack.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(422, detail=exc.errors()) from exc

    # Ensure unique rule_ids
    ids = [r.rule_id for r in pack.rules]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "Duplicate rule_id values are not allowed")

    saved = save_client_rules(slug, pack)

    with Session(get_engine()) as session:
        client = session.exec(select(Client).where(Client.slug == slug)).first()
        if client:
            client.rules_version = saved.version
            session.add(client)
            session.commit()

    return {
        "pack": saved.model_dump(mode="json"),
        "style_excerpt": load_style_excerpt(slug),
        "saved": True,
    }


@router.put("/clients/{slug}/style-excerpt")
def put_style_excerpt(slug: str, body: StyleExcerptUpdate) -> dict[str, Any]:
    seed_sgs()
    try:
        load_client_rules(slug)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    text = save_style_excerpt(slug, body.text)
    return {"style_excerpt": text, "saved": True}
