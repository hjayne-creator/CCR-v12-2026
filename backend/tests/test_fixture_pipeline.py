"""Offline fixture path: stages 1–4 without live APIs or LLMs for facts fixture."""
from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.config import get_settings
from app.models.db import Client, Run, Source, get_engine, init_db
from app.pipeline.stages import stage01_scrape_subject, stage02_research, stage03_scrape_sources, stage04_facts
from app.seed import seed_sgs


@pytest.mark.asyncio
async def test_fixture_scrape_research_sources_facts(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("USE_FIXTURES", "true")
    get_settings.cache_clear()

    # Re-init engine against temp db
    import app.models.db as dbmod

    dbmod._engine = None
    init_db()
    client = seed_sgs()

    with Session(get_engine()) as session:
        run = Run(client_id=client.id, url="https://www.sgs-engineering.com/sgs-3-ton-low-profile-trolley-jack", status="running")
        session.add(run)
        session.commit()
        session.refresh(run)

        baseline = await stage01_scrape_subject(session, run, client, use_fixtures=True)
        assert "Trolley Jack" in baseline.title
        assert baseline.source_id

        plan = await stage02_research(
            session,
            run,
            client,
            baseline,
            use_fixtures=True,
            extract_provider="openai",
            extract_model="gpt-6-luna",
        )
        assert plan.identity.classification == "Brand"
        assert len(plan.sources) >= 1

        scraped = await stage03_scrape_sources(session, run, plan, use_fixtures=True)
        assert len(scraped) >= 1

        sources = session.exec(select(Source).where(Source.run_id == run.id)).all()
        # Rewrite facts fixture source_id=1 to actual subject source id
        subject = next(s for s in sources if s.role == "subject")
        from app.pipeline.fixtures import load_json
        from app.models.schemas import FactLedger
        from app.engine.validators import enforce_fact_excerpts

        data = load_json("facts.json")
        for c in data["claims"]:
            for e in c["evidence"]:
                e["source_id"] = subject.id
        ledger = enforce_fact_excerpts(FactLedger.model_validate(data), {s.id: s.markdown for s in sources})
        assert ledger.verified_count >= 5
        assert any(c.status == "EXCLUDED" for c in ledger.claims)

    get_settings.cache_clear()
