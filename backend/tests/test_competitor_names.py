from app.engine.competitor_names import extract_competitor_name_tokens
from app.engine.rules import load_client_rules
from app.engine.validators import ValidationContext, draft_body_plaintext, run_code_validators
from app.models.schemas import FaqOut, FeatureItem, PdpDraft, SpecRow, TextBlock


def test_run9_petrol_not_treated_as_competitor():
    """Regression: same SGS product on retailers must not yield 'Petrol' as a competitor name."""
    names = extract_competitor_name_tokens(
        competitor_sources=[
            {"domain": "diy.com", "title": "SGS 45cc Petrol Chainsaw, Powerful Premium Bar & Chain"},
            {"domain": "pricerunner.com", "title": "SGS 45cc Petrol Chainsaw 15in Bar • See best price »"},
            {"domain": "feefo.com", "title": "SGS 45cc Petrol Chainsaw - 15in Bar Reviews | SGS Engineering"},
        ],
        subject_title="SGS 45cc Petrol Chainsaw - 15in Bar - SGS",
        owned_brands=["SGS", "NitroLift", "Rikä", "Rika"],
        subject_domain="sgs-engineering.com",
    )
    lowered = {n.lower() for n in names}
    assert "petrol" not in lowered
    assert "sgs" not in lowered
    assert "powerful" not in lowered
    assert "premium" not in lowered
    assert names == []


def test_real_competitor_brand_is_kept():
    names = extract_competitor_name_tokens(
        competitor_sources=[
            {"domain": "makita.co.uk", "title": "Makita 18V Cordless Chainsaw DUC254"},
        ],
        subject_title="SGS 45cc Petrol Chainsaw - 15in Bar",
        owned_brands=["SGS"],
        subject_domain="sgs-engineering.com",
    )
    lowered = {n.lower() for n in names}
    assert "makita" in lowered
    assert "petrol" not in lowered


def test_sty003_passes_when_petrol_in_faq():
    pack = load_client_rules("sgs-engineering")
    draft = PdpDraft(
        title="SGS 45cc Petrol Chainsaw - 15in Oregon Bar",
        overview=[TextBlock(text="A petrol chainsaw for tough wood.", claim_ids=["C1"])],
        features=[FeatureItem(feature="Recoil start", benefit="Easy starting", claim_ids=["C1"])],
        specifications=[SpecRow(attribute="Engine", value="45cc", claim_ids=["C1"])],
        faqs=[
            FaqOut(question="Is it petrol or electric?", answer="It is a petrol chainsaw.", claim_ids=["C1"]),
            FaqOut(question="Bar size?", answer="15 inch bar.", claim_ids=["C1"]),
            FaqOut(question="Weight?", answer="6.75 kg.", claim_ids=["C1"]),
        ],
    )
    names = extract_competitor_name_tokens(
        competitor_sources=[
            {"domain": "diy.com", "title": "SGS 45cc Petrol Chainsaw, Powerful Premium Bar & Chain"},
        ],
        subject_title=draft.title,
        owned_brands=["SGS"],
        subject_domain="sgs-engineering.com",
    )
    assert "Petrol" not in names and "petrol" not in {n.lower() for n in names}
    # Body contains petrol — must not fail STY-003 via false competitor token
    assert "petrol" in draft_body_plaintext(draft).lower()
    out = run_code_validators(
        pack,
        ValidationContext(draft=draft, competitor_names=names),
        apply_fixes=True,
    )
    by_id = {r.rule_id: r for r in out.results}
    assert by_id["STY-003"].status == "PASS"
