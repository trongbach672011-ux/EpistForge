"""Strict Pydantic models for the protocol foundation.

This module deliberately contains data contracts only. Persistence, graph
storage, and client adapters belong to later layers.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Annotated, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, field_validator


class ProtocolModel(BaseModel):
    """Common strict configuration for protocol objects."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        validate_assignment=True,
    )


class ResearchState(str, Enum):
    IDEA = "IDEA"
    HYPOTHESIS = "HYPOTHESIS"
    CRITIQUED = "CRITIQUED"
    TESTABLE = "TESTABLE"
    EXPERIMENT_REGISTERED = "EXPERIMENT_REGISTERED"
    EXECUTED = "EXECUTED"
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    VERIFIED = "VERIFIED"
    DISPUTED = "DISPUTED"
    NOVELTY_CHECKED = "NOVELTY_CHECKED"
    PROVISIONAL_KNOWLEDGE = "PROVISIONAL_KNOWLEDGE"
    REJECTED = "REJECTED"
    RETRACTED = "RETRACTED"


class EvidenceDirection(str, Enum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"


class EvidenceStrength(str, Enum):
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"


class VerificationVerdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIAL = "PARTIAL"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT = "INSUFFICIENT"


class IssueSeverity(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class NoveltyStatus(str, Enum):
    KNOWN = "KNOWN"
    INCREMENTAL = "INCREMENTAL"
    POSSIBLY_NOVEL = "POSSIBLY_NOVEL"
    UNCLEAR = "UNCLEAR"
    UNCHECKED = "UNCHECKED"


ScalarValue: TypeAlias = StrictStr | StrictInt | StrictFloat | StrictBool
HashValue: TypeAlias = Annotated[str, Field(pattern=r"^[0-9a-fA-F]{64}$")]


def _non_blank(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


class Hypothesis(ProtocolModel):
    id: str
    version: int
    statement: str
    mechanism: str
    assumptions: list[str]
    predictions: list[str]
    falsifiers: list[str]
    required_evidence: list[str]
    created_by: str
    status: ResearchState

    _non_blank_fields = field_validator(
        "id", "statement", "mechanism", "created_by", mode="after"
    )(_non_blank)


class Critique(ProtocolModel):
    target_id: str
    author: str
    fatal_issues: list[str]
    nonfatal_issues: list[str]
    verdict: str

    _non_blank_fields = field_validator("target_id", "author", "verdict", mode="after")(
        _non_blank
    )


class Experiment(ProtocolModel):
    id: str
    hypothesis_id: str
    hypothesis_version: int
    registered_before_run: bool
    baselines: list[str]
    controls: list[str]
    metrics: list[str]
    success_thresholds: dict[str, ScalarValue]
    failure_thresholds: dict[str, ScalarValue]
    seeds: list[int]
    ablations: list[str]
    required_artifacts: list[str]
    revision: int

    _non_blank_fields = field_validator("id", "hypothesis_id", mode="after")(_non_blank)


class Artifact(ProtocolModel):
    id: str
    type: str
    created_by: str
    input_ids: list[str]
    tool: str
    tool_version: str
    config_hash: HashValue
    content_hash: HashValue
    path: str

    _non_blank_fields = field_validator(
        "id", "type", "created_by", "tool", "tool_version", "path", mode="after"
    )(_non_blank)


class Evidence(ProtocolModel):
    id: str
    finding_id: str
    artifact_ids: list[str]
    direction: EvidenceDirection
    strength: EvidenceStrength
    conditions: list[str]

    _non_blank_fields = field_validator("id", "finding_id", mode="after")(_non_blank)


class Claim(ProtocolModel):
    id: str
    text: str
    scope: dict[str, ScalarValue]
    evidence_ids: list[str]
    verification_ids: list[str]
    status: ResearchState

    _non_blank_fields = field_validator("id", "text", mode="after")(_non_blank)


class VerificationIssue(ProtocolModel):
    severity: IssueSeverity
    description: str
    resolved: bool

    _non_blank_fields = field_validator("description", mode="after")(_non_blank)


class Verification(ProtocolModel):
    id: str
    experiment_id: str
    verifier: str
    blind_initial_verdict: bool
    recomputed_metrics: dict[str, ScalarValue]
    recompute_explanation: str = ""
    issues: list[VerificationIssue]
    verdict: VerificationVerdict
    spec_compliance: bool

    _non_blank_fields = field_validator("id", "experiment_id", "verifier", mode="after")(
        _non_blank
    )


class NoveltyReport(ProtocolModel):
    claim_id: str
    queries: list[str]
    sources_checked: list[str]
    closest_prior_work: list[str]
    differences: list[str]
    status: NoveltyStatus
    coverage_limits: list[str]
    search_date: date
    wording_within_coverage: bool
    no_prior_work_found: bool = False

    _non_blank_fields = field_validator("claim_id", mode="after")(_non_blank)


class WritingDraft(ProtocolModel):
    major_claim_ids: list[str]
    referenced_claim_ids: list[str]
    validated_claim_ids: list[str]
    limitations: list[str]
    disputed_claim_ids: list[str]
    writer_created_claim_ids: list[str]
