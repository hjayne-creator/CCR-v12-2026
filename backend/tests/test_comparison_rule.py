from app.engine.comparison import (
    brand_model_label,
    drop_incomplete_comparison_rows,
    extract_spec_keys,
    suitable_alternatives,
)
from app.engine.rules import load_client_rules
from app.engine.validators import ValidationContext, run_code_validators
from app.models.schemas import (
    Claim,
    ComparisonRow,
    ComparisonTable,
    Evidence,
    FactLedger,
    FeatureItem,
    PdpDraft,
    SpecRow,
    TextBlock,
)


def _base_draft(**kwargs) -> PdpDraft:
    data = dict(
        title="SGS 3 Ton Jack",
        overview=[TextBlock(text="A trolley jack.", claim_ids=["C1"])],
        features=[FeatureItem(feature="Low profile", benefit="Fits lowered cars", claim_ids=["C1"])],
        specifications=[SpecRow(attribute="Capacity", value="3 tonne", claim_ids=["C1"])],
    )
    data.update(kwargs)
    return PdpDraft(**data)


def test_brand_model_label_prefers_short_core():
    label = brand_model_label(
        "SGS 3 Ton Low Profile Trolley Jack | Free Delivery | Buy Online",
        brand_hints=["SGS"],
    )
    assert label.startswith("SGS")
    assert "Free Delivery" not in label
    assert len(label) < 80


def test_extract_spec_keys_finds_capacity_and_height():
    keys = extract_spec_keys(["Capacity: 3 tonne", "Minimum height 85mm", "Safety overload valve"])
    assert "capacity" in keys
    assert "min_height" in keys or "dimensions" in keys
    assert "safety" in keys


def test_suitable_alternatives_requires_overlap():
    ledger = FactLedger(
        claims=[
            Claim(
                claim_id="S1",
                statement="Capacity is 3 tonne",
                claim_type="spec",
                evidence=[Evidence(source_id=1, source_label="subject", excerpt="Capacity: 3 tonne")],
                status="VERIFIED",
            ),
            Claim(
                claim_id="S2",
                statement="Minimum height is 85mm",
                claim_type="spec",
                evidence=[Evidence(source_id=1, source_label="subject", excerpt="Minimum height: 85mm")],
                status="VERIFIED",
            ),
            Claim(
                claim_id="A1",
                statement="Capacity 3 tonne",
                claim_type="spec",
                evidence=[Evidence(source_id=2, source_label="alt", excerpt="Capacity 3 tonne")],
                status="VERIFIED",
            ),
            Claim(
                claim_id="A2",
                statement="Min height 80mm",
                claim_type="spec",
                evidence=[Evidence(source_id=2, source_label="alt", excerpt="Min height 80mm")],
                status="VERIFIED",
            ),
            Claim(
                claim_id="B1",
                statement="Includes carry case",
                claim_type="package_contents",
                evidence=[Evidence(source_id=3, source_label="weak", excerpt="Includes carry case")],
                status="VERIFIED",
            ),
        ]
    )
    alts = [
        {"source_id": 2, "title": "Alt A", "label": "Alt A"},
        {"source_id": 3, "title": "Alt B", "label": "Alt B"},
    ]
    suitable = suitable_alternatives(
        ledger=ledger,
        alternatives=alts,
        subject_source_id=1,
        min_overlap=2,
    )
    assert [a["source_id"] for a in suitable] == [2]


def test_drop_incomplete_rows():
    table = ComparisonTable(
        columns=["SGS", "A", "B"],
        rows=[
            ComparisonRow(dimension="Capacity", values=["3t", "3t", "2.5t"]),
            ComparisonRow(dimension="Height", values=["85mm", "", "90mm"]),
        ],
    )
    cleaned, dropped = drop_incomplete_comparison_rows(table)
    assert dropped == 1
    assert cleaned is not None
    assert len(cleaned.rows) == 1
    assert cleaned.rows[0].dimension == "Capacity"


def test_cmp001_skips_when_insufficient_alternatives():
    pack = load_client_rules("sgs-engineering")
    draft = _base_draft(comparison=None)
    out = run_code_validators(
        pack,
        ValidationContext(draft=draft, alternative_count=2, comparison_eligible=False),
        apply_fixes=True,
    )
    by_id = {r.rule_id: r for r in out.results}
    assert by_id["CMP-001"].status == "SKIP"
    assert "suitable" in by_id["CMP-001"].evidence


def test_cmp001_removes_table_when_insufficient():
    pack = load_client_rules("sgs-engineering")
    draft = _base_draft(
        comparison=ComparisonTable(
            columns=["Subject", "A", "B"],
            rows=[ComparisonRow(dimension="Capacity", values=["3t", "3t", "2.5t"])],
        )
    )
    out = run_code_validators(
        pack,
        ValidationContext(draft=draft, alternative_count=2, comparison_eligible=False),
        apply_fixes=True,
    )
    by_id = {r.rule_id: r for r in out.results}
    assert out.draft is not None
    assert out.draft.comparison is None
    assert by_id["CMP-001"].status == "PASS"
    assert by_id["CMP-001"].auto_fixed


def test_cmp001_drops_incomplete_rows_then_passes():
    pack = load_client_rules("sgs-engineering")
    draft = _base_draft(
        comparison=ComparisonTable(
            columns=["SGS Jack", "Alt One", "Alt Two", "Alt Three"],
            rows=[
                ComparisonRow(dimension="Capacity", values=["3 tonne", "3 tonne", "2.5 tonne", "3 tonne"]),
                ComparisonRow(dimension="Warranty", values=["1 year", "", "1 year", "2 year"]),
            ],
            claim_ids=["C1"],
        )
    )
    out = run_code_validators(
        pack,
        ValidationContext(draft=draft, alternative_count=3, comparison_eligible=True),
        apply_fixes=True,
    )
    by_id = {r.rule_id: r for r in out.results}
    assert out.draft is not None
    assert out.draft.comparison is not None
    assert len(out.draft.comparison.rows) == 1
    assert by_id["CMP-001"].status == "PASS"


def test_cmp001_requires_table_when_eligible():
    pack = load_client_rules("sgs-engineering")
    draft = _base_draft(comparison=None)
    out = run_code_validators(
        pack,
        ValidationContext(draft=draft, alternative_count=3, comparison_eligible=True),
        apply_fixes=True,
    )
    by_id = {r.rule_id: r for r in out.results}
    assert by_id["CMP-001"].status == "FAIL"


def test_cmp001_passes_well_formed_table():
    pack = load_client_rules("sgs-engineering")
    draft = _base_draft(
        comparison=ComparisonTable(
            columns=["SGS Jack", "Alt One", "Alt Two", "Alt Three"],
            rows=[
                ComparisonRow(dimension="Capacity", values=["3 tonne", "3 tonne", "2.5 tonne", "3 tonne"]),
                ComparisonRow(dimension="Min height", values=["85mm", "80mm", "90mm", "90mm"]),
            ],
            claim_ids=["C1"],
        )
    )
    out = run_code_validators(
        pack,
        ValidationContext(draft=draft, alternative_count=3, comparison_eligible=True),
        apply_fixes=True,
    )
    by_id = {r.rule_id: r for r in out.results}
    assert by_id["CMP-001"].status == "PASS"
