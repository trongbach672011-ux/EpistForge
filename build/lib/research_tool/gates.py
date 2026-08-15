"""Machine-checkable promotion and writing gates."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Sequence
import re

from .models import (
    Artifact,
    Claim,
    Evidence,
    Experiment,
    Hypothesis,
    IssueSeverity,
    NoveltyReport,
    NoveltyStatus,
    ResearchState,
    Verification,
    WritingDraft,
)


@dataclass(frozen=True, slots=True)
class GateResult:
    """Stable, serializable-enough result for a protocol gate."""

    passed: bool
    failures: tuple[str, ...] = ()

    @property
    def errors(self) -> tuple[str, ...]:
        return self.failures

    def __bool__(self) -> bool:
        return self.passed


def _result(failures: list[str]) -> GateResult:
    return GateResult(passed=not failures, failures=tuple(failures))


def check_hypothesis_gate(
    hypothesis: Hypothesis,
    *,
    fatal_critique_issues: Sequence[str] = (),
) -> GateResult:
    failures: list[str] = []
    if not hypothesis.mechanism.strip():
        failures.append("mechanism is required")
    if not hypothesis.predictions:
        failures.append("at least one prediction is required")
    if not hypothesis.falsifiers:
        failures.append("at least one falsifier is required")
    if not hypothesis.assumptions:
        failures.append("assumptions must be recorded")
    if fatal_critique_issues:
        failures.append("unresolved fatal critique issues exist")
    return _result(failures)


def check_experiment_gate(experiment: Experiment) -> GateResult:
    failures: list[str] = []
    if not experiment.registered_before_run:
        failures.append("experiment must be registered before execution")
    if not experiment.baselines:
        failures.append("at least one baseline with rationale is required")
    if not experiment.controls:
        failures.append("at least one control with rationale is required")
    if not experiment.metrics:
        failures.append("at least one metric is required")
    if not experiment.required_artifacts:
        failures.append("expected artifacts must be declared")

    for metric in experiment.metrics:
        if metric not in experiment.success_thresholds:
            failures.append(f"missing success threshold for metric: {metric}")
        if metric not in experiment.failure_thresholds:
            failures.append(f"missing failure threshold for metric: {metric}")
    return _result(failures)


_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def check_evidence_gate(
    evidence: Evidence,
    *,
    artifacts: Mapping[str, Artifact],
    finding_sources: Mapping[str, Sequence[str]],
) -> GateResult:
    failures: list[str] = []
    if not evidence.artifact_ids:
        failures.append("evidence must reference at least one artifact")
    missing_artifacts = [artifact_id for artifact_id in evidence.artifact_ids if artifact_id not in artifacts]
    if missing_artifacts:
        failures.append(f"missing artifact(s): {', '.join(missing_artifacts)}")
    invalid_hashes = [
        artifact_id
        for artifact_id in evidence.artifact_ids
        if artifact_id in artifacts
        and not _SHA256_RE.fullmatch(artifacts[artifact_id].content_hash)
    ]
    if invalid_hashes:
        failures.append(f"invalid artifact hash(es): {', '.join(invalid_hashes)}")
    if not finding_sources.get(evidence.finding_id):
        failures.append("finding must have at least one source")
    return _result(failures)


def check_verification_gate(
    verification: Verification,
    *,
    producer_agent_id: str,
) -> GateResult:
    failures: list[str] = []
    if verification.verifier == producer_agent_id:
        failures.append("verifier must be independent of the producer")
    if not verification.blind_initial_verdict:
        failures.append("blind initial verdict is required")
    if not verification.recomputed_metrics and not verification.recompute_explanation.strip():
        failures.append("recomputation or an explanation of why it was impossible is required")
    if not verification.spec_compliance:
        failures.append("experiment spec compliance must be checked")
    if any(
        issue.severity is IssueSeverity.P0 and not issue.resolved
        for issue in verification.issues
    ):
        failures.append("unresolved P0 verification issues exist")
    return _result(failures)


def check_novelty_gate(report: NoveltyReport) -> GateResult:
    failures: list[str] = []
    if report.status is NoveltyStatus.UNCHECKED:
        failures.append("novelty report has not been checked")
    if not report.queries:
        failures.append("query log is required")
    if not report.sources_checked:
        failures.append("searched sources must be recorded")
    if not report.closest_prior_work and not report.no_prior_work_found:
        failures.append("closest prior work or an explicit no-result record is required")
    if not report.coverage_limits:
        failures.append("coverage limitations are required")
    if not report.wording_within_coverage:
        failures.append("claim wording exceeds the recorded search coverage")
    return _result(failures)


def check_writing_gate(
    draft: WritingDraft,
    *,
    claims: Mapping[str, Claim],
) -> GateResult:
    failures: list[str] = []
    if not draft.limitations:
        failures.append("limitations are required")
    if draft.writer_created_claim_ids:
        failures.append("writer-created claims are forbidden")

    for claim_id in draft.referenced_claim_ids:
        if claim_id not in claims:
            failures.append(f"orphan claim reference: {claim_id}")
    for claim_id in draft.major_claim_ids:
        claim = claims.get(claim_id)
        if claim is None or claim_id not in draft.validated_claim_ids:
            failures.append(f"major claim is not a validated claim: {claim_id}")
        elif claim.status not in {
            ResearchState.VERIFIED,
            ResearchState.NOVELTY_CHECKED,
            ResearchState.PROVISIONAL_KNOWLEDGE,
        }:
            failures.append(f"major claim has non-promotable status: {claim_id}")
        if claim_id in draft.disputed_claim_ids:
            failures.append(f"disputed claim cannot be written as settled: {claim_id}")
    return _result(failures)
