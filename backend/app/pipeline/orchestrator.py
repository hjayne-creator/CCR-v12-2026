from __future__ import annotations

import logging
import traceback
from typing import Any

from sqlmodel import Session, select

from app.config import get_settings
from app.models.db import Client, Run, StageResult, get_engine, utcnow
from app.pipeline.fixtures import fixtures_enabled
from app.pipeline.stages import (
    STAGE_NAMES,
    stage01_scrape_subject,
    stage02_research,
    stage03_scrape_sources,
    stage04_facts,
    stage05_write,
    stage06_qc,
)

logger = logging.getLogger(__name__)


def _start_stage(session: Session, run: Run, stage: int) -> StageResult:
    row = StageResult(
        run_id=run.id,
        stage=stage,
        name=STAGE_NAMES[stage],
        status="running",
        started_at=utcnow(),
    )
    session.add(row)
    run.current_stage = stage
    run.status = "running"
    run.updated_at = utcnow()
    session.add(run)
    session.commit()
    session.refresh(row)
    return row


def _finish_stage(
    session: Session,
    row: StageResult,
    *,
    status: str,
    artifact: dict[str, Any] | None = None,
    gate: str | None = None,
    error: str | None = None,
) -> None:
    row.status = status
    row.artifact = artifact or {}
    row.gate = gate
    row.error = error
    row.finished_at = utcnow()
    if row.started_at:
        row.duration_ms = int((row.finished_at - row.started_at).total_seconds() * 1000)
    session.add(row)
    session.commit()


def _models(run: Run) -> dict[str, tuple[str, str]]:
    s = get_settings()
    defaults = {
        "writer": (s.default_writer_provider, s.default_writer_model),
        "qa": (s.default_qa_provider, s.default_qa_model),
        "extract": (s.default_extract_provider, s.default_extract_model),
    }
    overrides = run.model_overrides or {}
    out = {}
    for role, (prov, model) in defaults.items():
        if role in overrides and isinstance(overrides[role], dict):
            out[role] = (overrides[role].get("provider") or prov, overrides[role].get("model") or model)
        else:
            out[role] = (prov, model)
    return out


async def run_pipeline(run_id: int, *, use_fixtures: bool | None = None) -> None:
    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")
        client = session.get(Client, run.client_id)
        if not client:
            raise ValueError(f"Client {run.client_id} not found")

        fx = fixtures_enabled(use_fixtures if use_fixtures is not None else run.model_overrides.get("use_fixtures"))
        models = _models(run)

        try:
            # 1
            row = _start_stage(session, run, 1)
            baseline = await stage01_scrape_subject(session, run, client, use_fixtures=fx)
            _finish_stage(session, row, status="passed", artifact=baseline.model_dump(), gate="SCRAPE-01")
            session.refresh(run)

            # 2
            row = _start_stage(session, run, 2)
            plan = await stage02_research(
                session,
                run,
                client,
                baseline,
                use_fixtures=fx,
                extract_provider=models["extract"][0],
                extract_model=models["extract"][1],
            )
            run.identity_class = plan.identity.classification
            session.add(run)
            session.commit()
            _finish_stage(session, row, status="passed", artifact=plan.model_dump(), gate="RESEARCH-02")
            session.refresh(run)

            # 3
            row = _start_stage(session, run, 3)
            scraped = await stage03_scrape_sources(session, run, plan, use_fixtures=fx)
            _finish_stage(session, row, status="passed", artifact={"sources": scraped}, gate="SCRAPE-03")
            session.refresh(run)

            # 4
            row = _start_stage(session, run, 4)
            ledger = await stage04_facts(
                session,
                run,
                client,
                extract_provider=models["extract"][0],
                extract_model=models["extract"][1],
                use_fixtures=fx,
            )
            if ledger.verified_count == 0:
                _finish_stage(
                    session,
                    row,
                    status="failed",
                    artifact=ledger.model_dump(),
                    gate="FACTS-04",
                    error="No verified claims after enforcement",
                )
                run.status = "failed"
                run.error = "No verified claims"
                run.updated_at = utcnow()
                session.add(run)
                session.commit()
                return
            _finish_stage(session, row, status="passed", artifact=ledger.model_dump(), gate="FACTS-04")
            session.refresh(run)

            # 5
            row = _start_stage(session, run, 5)
            draft = await stage05_write(
                session,
                run,
                client,
                ledger,
                writer_provider=models["writer"][0],
                writer_model=models["writer"][1],
                use_fixtures=fx,
            )
            _finish_stage(session, row, status="passed", artifact=draft.model_dump(), gate="WRITE-05")
            session.refresh(run)

            # 6
            row = _start_stage(session, run, 6)
            qc = await stage06_qc(
                session,
                run,
                client,
                ledger,
                draft,
                plan,
                qa_provider=models["qa"][0],
                qa_model=models["qa"][1],
                use_fixtures=fx,
            )
            released = qc.compliance.disposition == "RELEASE"
            _finish_stage(
                session,
                row,
                status="passed" if released or qc.compliance.disposition == "HOLD" else "failed",
                artifact=qc.model_dump(),
                gate="QC-06",
            )
            session.refresh(run)
            run.status = "released" if released else ("completed" if qc.compliance.disposition == "HOLD" else "failed")
            run.released = released
            run.completed_at = utcnow()
            run.updated_at = utcnow()
            run.current_stage = 6
            if not released and qc.compliance.disposition == "REJECT":
                run.error = "Mandatory compliance rules failed"
            session.add(run)
            session.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Pipeline failed for run %s", run_id)
            run = session.get(Run, run_id)
            if run:
                run.status = "failed"
                run.error = str(exc)
                run.updated_at = utcnow()
                session.add(run)
                # mark current stage failed if running
                stage_row = session.exec(
                    select(StageResult)
                    .where(StageResult.run_id == run_id, StageResult.status == "running")
                    .order_by(StageResult.stage.desc())
                ).first()
                if stage_row:
                    _finish_stage(
                        session,
                        stage_row,
                        status="failed",
                        error=str(exc),
                        artifact={"traceback": traceback.format_exc()[-2000:]},
                    )
                session.commit()
            raise
