from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlmodel import Session, select

from app.adapters.llm import catalog
from app.models.db import Client, LlmUsage, Run, Source, StageResult, get_engine
from app.models.schemas import CreateRunRequest, RunSummary
from app.pipeline.orchestrator import run_pipeline
from app.seed import seed_sgs

router = APIRouter(prefix="/api", tags=["runs"])


def _summary(run: Run) -> RunSummary:
    return RunSummary(
        id=run.id,
        url=run.url,
        status=run.status,
        current_stage=run.current_stage,
        identity_class=run.identity_class,
        cost_usd=round(run.cost_usd, 6),
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        released=run.released,
        error=run.error,
        created_at=run.created_at.isoformat(),
        updated_at=run.updated_at.isoformat(),
    )


@router.get("/models")
def list_models() -> dict[str, Any]:
    return {"providers": catalog()}


@router.get("/clients")
def list_clients() -> list[dict[str, Any]]:
    seed_sgs()
    with Session(get_engine()) as session:
        clients = session.exec(select(Client)).all()
        return [
            {
                "id": c.id,
                "slug": c.slug,
                "name": c.name,
                "domain": c.domain,
                "rules_version": c.rules_version,
                "owned_brands": c.owned_brands,
                "max_words": c.max_words,
                "title_max_chars": c.title_max_chars,
            }
            for c in clients
        ]


@router.get("/runs", response_model=list[RunSummary])
def list_runs() -> list[RunSummary]:
    with Session(get_engine()) as session:
        runs = session.exec(select(Run).order_by(Run.id.desc()).limit(50)).all()
        return [_summary(r) for r in runs]


@router.post("/runs", response_model=RunSummary)
async def create_run(body: CreateRunRequest, background: BackgroundTasks) -> RunSummary:
    seed_sgs()
    with Session(get_engine()) as session:
        client = session.exec(select(Client).where(Client.slug == body.client_slug)).first()
        if not client:
            raise HTTPException(404, f"Client {body.client_slug} not found")

        overrides: dict[str, Any] = {}
        if body.writer:
            overrides["writer"] = body.writer.model_dump()
        if body.qa:
            overrides["qa"] = body.qa.model_dump()
        if body.extract:
            overrides["extract"] = body.extract.model_dump()
        if body.use_fixtures is not None:
            overrides["use_fixtures"] = body.use_fixtures

        run = Run(
            client_id=client.id,
            url=body.url.strip(),
            status="pending",
            model_overrides=overrides,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id
        summary = _summary(run)

    background.add_task(_bg_run, run_id, body.use_fixtures)
    return summary


async def _bg_run(run_id: int, use_fixtures: bool | None) -> None:
    try:
        await run_pipeline(run_id, use_fixtures=use_fixtures)
    except Exception:  # noqa: BLE001
        # orchestrator already persists failure
        pass


@router.get("/runs/{run_id}")
def get_run(run_id: int) -> dict[str, Any]:
    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if not run:
            raise HTTPException(404, "Run not found")
        stages = session.exec(
            select(StageResult).where(StageResult.run_id == run_id).order_by(StageResult.stage)
        ).all()
        sources = session.exec(select(Source).where(Source.run_id == run_id)).all()
        usage = session.exec(select(LlmUsage).where(LlmUsage.run_id == run_id)).all()
        client = session.get(Client, run.client_id)

        qc = next((s for s in stages if s.stage == 6), None)
        facts = next((s for s in stages if s.stage == 4), None)
        write = next((s for s in stages if s.stage == 5), None)

        return {
            "run": _summary(run).model_dump(),
            "client": {"slug": client.slug, "name": client.name} if client else None,
            "stages": [
                {
                    "stage": s.stage,
                    "name": s.name,
                    "status": s.status,
                    "gate": s.gate,
                    "error": s.error,
                    "duration_ms": s.duration_ms,
                    "artifact": s.artifact if s.stage != 1 else {
                        **{k: v for k, v in (s.artifact or {}).items() if k != "markdown_excerpt"},
                        "markdown_excerpt": ((s.artifact or {}).get("markdown_excerpt") or "")[:500],
                    },
                }
                for s in stages
            ],
            "sources": [
                {
                    "id": src.id,
                    "url": src.url,
                    "role": src.role,
                    "domain": src.domain,
                    "title": src.title,
                    "markdown_chars": len(src.markdown or ""),
                }
                for src in sources
            ],
            "usage": [
                {
                    "stage": u.stage,
                    "provider": u.provider,
                    "model": u.model,
                    "role": u.role,
                    "input_tokens": u.input_tokens,
                    "output_tokens": u.output_tokens,
                    "cost_usd": round(u.cost_usd, 6),
                }
                for u in usage
            ],
            "fact_ledger": (facts.artifact if facts else None),
            "draft": (write.artifact if write and not qc else None) or ((qc.artifact or {}).get("draft") if qc else None),
            "compliance": ((qc.artifact or {}).get("compliance") if qc else None),
            "repairs": ((qc.artifact or {}).get("repairs") if qc else None),
        }


@router.post("/runs/{run_id}/rerun")
async def rerun(run_id: int, background: BackgroundTasks) -> RunSummary:
    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if not run:
            raise HTTPException(404, "Run not found")
        # Create a new run cloning URL/models
        new_run = Run(
            client_id=run.client_id,
            url=run.url,
            status="pending",
            model_overrides=run.model_overrides,
        )
        session.add(new_run)
        session.commit()
        session.refresh(new_run)
        summary = _summary(new_run)
        new_id = new_run.id
        use_fx = (run.model_overrides or {}).get("use_fixtures")
    background.add_task(_bg_run, new_id, use_fx)
    return summary
