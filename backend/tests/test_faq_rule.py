from app.engine.faq_research import extract_question_seeds, research_faq_context
from app.engine.rules import load_client_rules
from app.engine.validators import ValidationContext, run_code_validators
from app.models.db import Source
from app.models.schemas import (
    Claim,
    Evidence,
    FactLedger,
    FaqOut,
    FeatureItem,
    PdpDraft,
    SpecRow,
    TextBlock,
)


def _draft(faqs: list[FaqOut]) -> PdpDraft:
    return PdpDraft(
        title="SGS 3 Ton Jack",
        overview=[TextBlock(text="A trolley jack.", claim_ids=["C1"])],
        features=[FeatureItem(feature="Low profile", benefit="Clearance", claim_ids=["C1"])],
        specifications=[SpecRow(attribute="Capacity", value="3 tonne", claim_ids=["C1"])],
        faqs=faqs,
    )


def _ledger() -> FactLedger:
    return FactLedger(
        claims=[
            Claim(
                claim_id="C1",
                statement="Capacity is 3 tonne",
                claim_type="spec",
                evidence=[Evidence(source_id=1, source_label="s", excerpt="Capacity: 3 tonne")],
                status="VERIFIED",
            )
        ],
        gaps=["Competitor mentions dual pump"],
        verified_count=1,
    )


def test_extract_question_seeds():
    md = "# FAQ\nWhat is the capacity?\n\nSome text.\nHow high does it lift?\n"
    seeds = extract_question_seeds(md)
    assert "What is the capacity?" in seeds
    assert "How high does it lift?" in seeds


def test_research_faq_context_includes_gaps_and_seeds():
    ledger = _ledger()
    sources = [
        Source(
            run_id=1,
            url="https://example.test/p",
            role="subject",
            markdown="What ground clearance is required?\nCapacity: 3 tonne",
        )
    ]
    ctx = research_faq_context(ledger=ledger, sources=sources)
    assert "Competitor mentions dual pump" in ctx["research_gaps"]
    assert any("ground clearance" in q.lower() for q in ctx["research_question_seeds"])


def test_faq001_fails_when_too_few():
    pack = load_client_rules("sgs-engineering")
    draft = _draft(
        [
            FaqOut(question="Q1?", answer="A1", claim_ids=["C1"]),
            FaqOut(question="Q2?", answer="A2", claim_ids=["C1"]),
        ]
    )
    out = run_code_validators(
        pack,
        ValidationContext(draft=draft, ledger=_ledger()),
        apply_fixes=True,
    )
    by_id = {r.rule_id: r for r in out.results}
    assert by_id["FAQ-001"].status == "FAIL"


def test_faq001_passes_with_four():
    pack = load_client_rules("sgs-engineering")
    draft = _draft(
        [
            FaqOut(question="What is the capacity?", answer="3 tonne.", claim_ids=["C1"]),
            FaqOut(question="What clearance is needed?", answer="Low profile design.", claim_ids=["C1"]),
            FaqOut(question="Is overload protection included?", answer="Yes.", claim_ids=["C1"]),
            FaqOut(question="What is the max lift?", answer="See verified specs.", claim_ids=["C1"]),
        ]
    )
    out = run_code_validators(
        pack,
        ValidationContext(draft=draft, ledger=_ledger()),
        apply_fixes=True,
    )
    by_id = {r.rule_id: r for r in out.results}
    assert by_id["FAQ-001"].status == "PASS"


def test_faq001_rejects_duplicates():
    pack = load_client_rules("sgs-engineering")
    draft = _draft(
        [
            FaqOut(question="What is the capacity?", answer="3 tonne.", claim_ids=["C1"]),
            FaqOut(question="What is the capacity?", answer="Three tonne.", claim_ids=["C1"]),
            FaqOut(question="Max lift?", answer="500mm.", claim_ids=["C1"]),
        ]
    )
    out = run_code_validators(
        pack,
        ValidationContext(draft=draft, ledger=_ledger()),
        apply_fixes=True,
    )
    by_id = {r.rule_id: r for r in out.results}
    assert by_id["FAQ-001"].status == "FAIL"
    assert "duplicate" in by_id["FAQ-001"].evidence.lower()
