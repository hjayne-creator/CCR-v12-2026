"""Full offline pipeline through QC using fixtures (no live APIs / LLMs)."""
from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.config import get_settings
from app.models.db import Run, StageResult, get_engine, init_db
from app.pipeline.orchestrator import run_pipeline
from app.seed import seed_sgs


@pytest.mark.asyncio
async def test_full_fixture_pipeline(tmp_path, monkeypatch):
    db_path = tmp_path / "e2e.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("USE_FIXTURES", "true")
    get_settings.cache_clear()

    import app.models.db as dbmod

    dbmod._engine = None
    init_db()
    client = seed_sgs()

    with Session(get_engine()) as session:
        run = Run(
            client_id=client.id,
            url="https://www.sgs-engineering.com/sgs-3-ton-low-profile-trolley-jack",
            status="pending",
            model_overrides={"use_fixtures": True},
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id

    await run_pipeline(run_id, use_fixtures=True)

    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        assert run is not None
        assert run.status in {"released", "completed", "failed"}
        stages = session.exec(select(StageResult).where(StageResult.run_id == run_id).order_by(StageResult.stage)).all()
        assert [s.stage for s in stages] == [1, 2, 3, 4, 5, 6]
        assert all(s.status in {"passed", "failed"} for s in stages)
        qc = next(s for s in stages if s.stage == 6)
        compliance = (qc.artifact or {}).get("compliance") or {}
        results = compliance.get("results") or []
        rule_ids = {r["rule_id"] for r in results}
        for required in ("ACC-003", "STY-001", "STY-002", "SEO-001", "SEO-002", "FMT-001"):
            assert required in rule_ids
        assert compliance.get("disposition") in {"RELEASE", "HOLD", "REJECT"}
        assert (qc.artifact or {}).get("draft", {}).get("title")

    get_settings.cache_clear()
