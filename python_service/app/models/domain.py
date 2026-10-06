"""Domain models used inside agent workflows (validated with Pydantic)."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ExtractedLineItem(BaseModel):
    line_item_id: str | None = None
    product_name: str | None = None
    sku: str | None = None
    quantity: int = Field(default=1, ge=1)
    unit_price: Decimal
    total_price: Decimal | None = None

    @model_validator(mode="after")
    def _fill_totals(self) -> ExtractedLineItem:
        if self.total_price is None:
            self.total_price = self.unit_price * self.quantity
        return self


class ExtractedPO(BaseModel):
    po_number: str | None = None
    customer: str | None = None
    gst_no: str | None = None
    ship_to: str | None = None
    address_1: str | None = None
    address_2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    zip: str | None = None
    line_items: list[ExtractedLineItem] = Field(default_factory=list)

    @property
    def total_amount(self) -> Decimal:
        return sum((item.total_price or Decimal("0") for item in self.line_items), Decimal("0"))


class VerificationIssue(BaseModel):
    code: str
    message: str
    severity: Literal["error", "warning"] = "error"
    details: dict = Field(default_factory=dict)


class ValidationBranchResult(BaseModel):
    """Outcome of one independent verifier branch.

    ``details`` carries branch-specific observations (resolved ``customer_id``,
    catalogue price comparisons, applied policy keys) so the aggregate result
    stays a single normalized shape without inventing a model per branch.
    """

    branch: str
    passed: bool = False
    issues: list[VerificationIssue] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)

    @property
    def blocking_issues(self) -> list[VerificationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[VerificationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]


class VerificationResult(BaseModel):
    """Normalized verifier output consumed by ``POOrchestrator``.

    The three business validations run independently and are aggregated here
    into one result. The flat fields (``issues``, ``has_blocking_issues``,
    ``customer_verified``, ``products_*``, ``policy_applied``, ``checks``) are
    kept and populated by aggregation because downstream consumers
    (``SalesAgent``, HITL context) read them directly.
    """

    has_blocking_issues: bool = False
    issues: list[VerificationIssue] = Field(default_factory=list)
    customer_verified: bool = False
    customer_id: str | None = None
    products_verified: int = 0
    products_total: int = 0
    policy_applied: list[str] = Field(default_factory=list)
    checks: dict = Field(default_factory=dict)

    header_validation: ValidationBranchResult | None = None
    line_item_validation: ValidationBranchResult | None = None
    commercial_validation: ValidationBranchResult | None = None

    #: Split views of ``issues``, filled by aggregation. These are real fields
    #: rather than properties so they survive ``model_dump()`` and reach the
    #: orchestrator, logs, and HITL context as serialized data.
    blocking_issues: list[VerificationIssue] = Field(default_factory=list)
    warnings: list[VerificationIssue] = Field(default_factory=list)

    @property
    def branches(self) -> list[ValidationBranchResult]:
        return [
            branch
            for branch in (self.header_validation, self.line_item_validation, self.commercial_validation)
            if branch is not None
        ]

    @property
    def criteria_met(self) -> bool:
        return not self.has_blocking_issues


# --------------------------------------------------------------------------
# Extraction models (candidates, evidence, quality gate, episodic patterns)
# --------------------------------------------------------------------------


class ExtractedFieldValue(BaseModel):
    """A single persisted extracted value for one canonical field."""

    field_name: str
    value: str


class CandidateEvidence(BaseModel):
    """One piece of evidence supporting a candidate value."""

    kind: str = "semantic"  # semantic | contextual | format | relationship | db | negative
    label: str | None = None
    page: int | None = None
    location: str | None = None
    surrounding_text: str | None = None
    score: float = 0.0
    note: str | None = None


class ExtractionCandidate(BaseModel):
    """A plausible value for a field, with the evidence gathered for it."""

    field_name: str
    value: str
    source: str = "semantic"  # "episodic" | "semantic"
    source_label: str | None = None
    page: int | None = None
    location: str | None = None
    surrounding_text: str | None = None
    evidence: list[CandidateEvidence] = Field(default_factory=list)

    @property
    def evidence_score(self) -> float:
        if not self.evidence:
            return 0.0
        return round(sum(e.score for e in self.evidence) / len(self.evidence), 4)


class EvaluationVerdict(BaseModel):
    """Result of validating a candidate against accumulated evidence."""

    field_name: str
    accepted: bool = False
    score: float = 0.0
    sources: int = 0
    reasons: list[str] = Field(default_factory=list)
    resolved_value: str | None = None
    candidates: list[ExtractionCandidate] = Field(default_factory=list)
    ambiguous: bool = False


class QualityGateResult(BaseModel):
    """Final acceptance decision before persistence."""

    field_name: str
    passed: bool = False
    score: float = 0.0
    sources: int = 0
    separation: float = 0.0
    resolved_value: str | None = None
    reason: str | None = None


class EpisodicPattern(BaseModel):
    """Customer-specific extraction pattern (reusable knowledge, not a value)."""

    customer_id: str
    field_name: str
    field_id: str | None = None
    location_hint: str | None = None
    document_pattern: str | None = None
    instruction: str | None = None
    confidence: float = 0.5
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0


class MemoryBundle(BaseModel):
    """Procedural + semantic memory loaded from configuration for a field."""

    field_name: str
    procedure: list[str] = Field(default_factory=list)
    description: str | None = None
    possible_labels: list[str] = Field(default_factory=list)


class FieldExtractionOutcome(BaseModel):
    """Per-field extraction outcome with the persisted values."""

    field_name: str
    strategy: str = "semantic"  # "episodic" | "semantic"
    passed: bool = False
    candidates: int = 0
    retries: int = 0
    quality_gate: QualityGateResult | None = None
