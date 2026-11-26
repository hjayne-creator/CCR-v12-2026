from app.engine.rules import load_client_rules
from app.engine.validators import (
    ValidationContext,
    draft_to_plaintext,
    enforce_fact_excerpts,
    excerpt_supported,
    run_code_validators,
    uk_fix_text,
    word_count,
)
from app.models.schemas import (
    Claim,
    Evidence,
    FactLedger,
    FeatureItem,
    PdpDraft,
    SpecRow,
    TextBlock,
)


def test_load_sgs_rules():
    pack = load_client_rules("sgs-engineering")
    assert pack.client_slug == "sgs-engineering"
    ids = {r.rule_id for r in pack.rules}
    assert "STY-001" in ids
    assert "ACC-003" in ids
    assert "SEO-001" in ids


def test_uk_spelling():
    text, changes = uk_fix_text("The aluminum color center is optimized")
    assert "aluminium" in text
    assert "colour" in text
    assert "centre" in text
    assert "optimised" in text
    assert changes


def test_excerpt_supported():
    src = "Capacity: 3 tonne. Minimum height: 85mm."
    assert excerpt_supported("Capacity: 3 tonne", src)
    assert not excerpt_supported("Capacity: 5 tonne", src)


def test_enforce_fact_excerpts_excludes_bad_claims():
    ledger = FactLedger(
        claims=[
            Claim(
                claim_id="C1",
                statement="ok",
                evidence=[Evidence(source_id=1, source_label="s", excerpt="Capacity: 3 tonne")],
                status="VERIFIED",
            ),
            Claim(
                claim_id="C2",
                statement="bad",
                evidence=[Evidence(source_id=1, source_label="s", excerpt="NOT IN SOURCE")],
                status="VERIFIED",
            ),
        ]
    )
    out = enforce_fact_excerpts(ledger, {1: "Capacity: 3 tonne. Minimum height: 85mm."})
    assert out.verified_count == 1
    assert out.excluded_count == 1
    assert out.claims[1].status == "EXCLUDED"


def test_code_validators_title_banned_structure():
    pack = load_client_rules("sgs-engineering")
    draft = PdpDraft(
        title="SGS trolley jack " + ("specification-detail-" * 12),
        overview=[TextBlock(text="A color aluminum jack.", claim_ids=["C1"])],
        features=[FeatureItem(feature="Low profile", benefit="Fits lowered cars", claim_ids=["C1"])],
        specifications=[SpecRow(attribute="Capacity", value="3 tonne", claim_ids=["C1"])],
    )
    ledger = FactLedger(
        claims=[
            Claim(
                claim_id="C1",
                statement="Capacity 3 tonne",
                evidence=[Evidence(source_id=1, source_label="s", excerpt="Capacity: 3 tonne")],
                status="VERIFIED",
            )
        ],
        verified_count=1,
    )
    outcome = run_code_validators(
        pack,
        ValidationContext(
            draft=draft,
            ledger=ledger,
            source_texts={1: "Capacity: 3 tonne"},
            gaps=[],
        ),
        apply_fixes=True,
    )
    by_id = {r.rule_id: r for r in outcome.results}
    assert by_id["STY-001"].status == "PASS"
    assert by_id["STY-002"].status == "PASS"
    assert by_id["SEO-001"].status == "FAIL"  # still too long after banned-term strip
    assert "colour" in draft_to_plaintext(outcome.draft).lower() or "aluminium" in draft_to_plaintext(outcome.draft).lower()
    assert word_count(draft_to_plaintext(outcome.draft)) > 0
