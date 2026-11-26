from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# --- Rules --------------------------------------------------------------------------------------

Priority = Literal["MANDATORY", "PREFERRED"]
ValidationMethod = Literal["CODE", "LLM", "HYBRID"]
OnFailure = Literal["AUTO_CORRECT", "TARGETED_REPAIR", "FLAG", "FAIL"]
StageName = Literal["scrape_subject", "research", "scrape_sources", "facts", "write", "qc"]


class RuleDef(BaseModel):
    rule_id: str
    description: str
    priority: Priority = "MANDATORY"
    scope: list[str] = Field(default_factory=list)
    validation_method: ValidationMethod = "CODE"
    on_failure: OnFailure = "FAIL"
    params: dict[str, Any] = Field(default_factory=dict)


class ClientRulesPack(BaseModel):
    client_slug: str
    version: str
    hierarchy: list[str] = Field(default_factory=list)
    rules: list[RuleDef]


class RuleResult(BaseModel):
    rule_id: str
    description: str = ""
    status: Literal["PASS", "FAIL", "FLAG", "SKIP"]
    evidence: str = ""
    auto_fixed: bool = False


class ComplianceReport(BaseModel):
    disposition: Literal["RELEASE", "HOLD", "REJECT"]
    rules_evaluated: int = 0
    passed: int = 0
    failed: int = 0
    flagged: int = 0
    results: list[RuleResult] = Field(default_factory=list)
    rounds: int = 0
    notes: list[str] = Field(default_factory=list)


# --- Pipeline artifacts -------------------------------------------------------------------------

class SubjectBaseline(BaseModel):
    url: str
    title: str = ""
    domain: str = ""
    markdown_excerpt: str = ""
    source_id: Optional[int] = None
    product_hints: list[str] = Field(default_factory=list)


class IdentityResult(BaseModel):
    classification: Literal["Brand", "Reseller"]
    reason: str = ""
    brand_name: str = ""
    product_name: str = ""
    search_queries: list[str] = Field(default_factory=list)
    exact_seller_count: int = 0


class PlannedSource(BaseModel):
    url: str
    role: Literal["manufacturer", "competitor"]
    domain: str = ""
    title: str = ""
    reason: str = ""


class SourcePlan(BaseModel):
    identity: IdentityResult
    sources: list[PlannedSource] = Field(default_factory=list)
    search_provider: str = ""
    notes: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    source_id: int
    source_label: str
    excerpt: str


class Claim(BaseModel):
    claim_id: str
    statement: str
    claim_type: Literal[
        "spec", "feature", "benefit", "use_case", "faq_answer",
        "concern_response", "comparison", "site_benefit", "title_attribute",
        "package_contents", "warranty", "compatibility", "safety", "other",
    ] = "other"
    evidence: list[Evidence] = Field(default_factory=list)
    status: Literal["VERIFIED", "EXCLUDED"] = "VERIFIED"
    exclusion_reason: Optional[str] = None
    target_location: str = "overview"


class FactLedger(BaseModel):
    claims: list[Claim] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    enforcement_notes: list[str] = Field(default_factory=list)
    verified_count: int = 0
    excluded_count: int = 0


class TextBlock(BaseModel):
    text: str
    claim_ids: list[str] = Field(default_factory=list)


class FeatureItem(BaseModel):
    feature: str
    benefit: str = ""
    claim_ids: list[str] = Field(default_factory=list)


class SpecRow(BaseModel):
    attribute: str
    value: str
    claim_ids: list[str] = Field(default_factory=list)


class FaqOut(BaseModel):
    question: str
    answer: str
    claim_ids: list[str] = Field(default_factory=list)


class ComparisonRow(BaseModel):
    dimension: str
    values: list[str] = Field(
        description="One cell per column, same order as columns. Use empty string when a value is not verified for that product."
    )


class ComparisonTable(BaseModel):
    """Selection-aid table. Omit the whole object when fewer than min_alternatives qualify."""

    columns: list[str] = Field(
        description="First column is the subject product, then 3–5 alternatives (product titles)"
    )
    rows: list[ComparisonRow] = Field(default_factory=list)
    choose_if: list[str] = Field(
        default_factory=list,
        description="Optional one 'Choose this if…' line per column, same order as columns",
    )
    claim_ids: list[str] = Field(default_factory=list)
    omission_reason: str = Field(
        default="",
        description="When comparison is null/omitted at write time this is unused; kept for repairs",
    )


class PdpDraft(BaseModel):
    title: str
    overview: list[TextBlock] = Field(default_factory=list)
    features: list[FeatureItem] = Field(default_factory=list)
    specifications: list[SpecRow] = Field(default_factory=list)
    faqs: list[FaqOut] = Field(default_factory=list)
    comparison: Optional[ComparisonTable] = None
    site_benefits: list[TextBlock] = Field(default_factory=list)
    gaps_addressed: list[str] = Field(default_factory=list)
    word_count: int = 0


class QcArtifact(BaseModel):
    draft: PdpDraft
    compliance: ComplianceReport
    repairs: list[str] = Field(default_factory=list)


# --- API ----------------------------------------------------------------------------------------

class ModelChoice(BaseModel):
    provider: str
    model: str


class CreateRunRequest(BaseModel):
    url: str
    client_slug: str = "sgs-engineering"
    writer: Optional[ModelChoice] = None
    qa: Optional[ModelChoice] = None
    extract: Optional[ModelChoice] = None
    use_fixtures: Optional[bool] = None


class RunSummary(BaseModel):
    id: int
    url: str
    status: str
    current_stage: int
    identity_class: Optional[str] = None
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    released: bool = False
    error: Optional[str] = None
    created_at: str
    updated_at: str


class ClientOut(BaseModel):
    id: int
    slug: str
    name: str
    domain: str
    rules_version: str
    owned_brands: list[str] = Field(default_factory=list)
    max_words: int = 1500
    title_max_chars: int = 150
