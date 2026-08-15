from datetime import date

import pytest
from pydantic import ValidationError

from research_tool.gates import (
    check_evidence_gate,
    check_experiment_gate,
    check_hypothesis_gate,
    check_novelty_gate,
    check_verification_gate,
    check_writing_gate,
)
from research_tool.models import (
    Artifact,
    Claim,
    Evidence,
    EvidenceDirection,
    EvidenceStrength,
    Experiment,
    Hypothesis,
    IssueSeverity,
    NoveltyReport,
    NoveltyStatus,
    ResearchState,
    Verification,
    VerificationIssue,
    VerificationVerdict,
    WritingDraft,
)
from research_tool.transitions import is_allowed_transition, validate_transition


def valid_hypothesis(**overrides) -> Hypothesis:
    data = {
        "id": "H-001",
        "version": 1,
        "statement": "A improves B under condition C.",
        "mechanism": "A changes the measured process in a testable way.",
        "assumptions": ["C is held constant"],
        "predictions": ["P-001"],
        "falsifiers": ["F-001"],
        "required_evidence": ["E-001"],
        "created_by": "A1",
        "status": ResearchState.HYPOTHESIS,
    }
    data.update(overrides)
    return Hypothesis(**data)


def valid_experiment(**overrides) -> Experiment:
    data = {
        "id": "EXP-001",
        "hypothesis_id": "H-001",
        "hypothesis_version": 1,
        "registered_before_run": True,
        "baselines": ["baseline: established method"],
        "controls": ["control: unchanged input"],
        "metrics": ["accuracy"],
        "success_thresholds": {"accuracy": 0.9},
        "failure_thresholds": {"accuracy": 0.5},
        "seeds": [1, 2],
        "ablations": ["remove A"],
        "required_artifacts": ["ART-001"],
        "revision": 0,
    }
    data.update(overrides)
    return Experiment(**data)


def valid_artifact(**overrides) -> Artifact:
    data = {
        "id": "ART-001",
        "type": "raw_result",
        "created_by": "C2",
        "input_ids": [],
        "tool": "runner",
        "tool_version": "1.0",
        "config_hash": "a" * 64,
        "content_hash": "b" * 64,
        "path": "artifacts/ART-001.json",
    }
    data.update(overrides)
    return Artifact(**data)


def valid_verification(**overrides) -> Verification:
    data = {
        "id": "V-001",
        "experiment_id": "EXP-001",
        "verifier": "D1",
        "blind_initial_verdict": True,
        "recomputed_metrics": {"accuracy": 0.91},
        "recompute_explanation": "Metrics were recomputed from the raw artifact.",
        "issues": [],
        "verdict": VerificationVerdict.SUPPORTED,
        "spec_compliance": True,
    }
    data.update(overrides)
    return Verification(**data)


def test_models_require_fields_and_reject_coercion_and_extra_fields():
    with pytest.raises(ValidationError):
        Hypothesis(
            id="H-001",
            version="1",
            statement="statement",
            mechanism="mechanism",
            assumptions=["assumption"],
            predictions=["P-001"],
            falsifiers=["F-001"],
            required_evidence=[],
            created_by="A1",
            status=ResearchState.HYPOTHESIS,
        )

    with pytest.raises(ValidationError):
        valid_hypothesis(unexpected="not allowed")

    with pytest.raises(ValidationError):
        valid_hypothesis(statement="   ")


def test_allowed_state_transitions_are_explicit():
    assert is_allowed_transition(ResearchState.IDEA, ResearchState.HYPOTHESIS)
    assert is_allowed_transition(ResearchState.DISPUTED, ResearchState.RETRACTED)
    assert not is_allowed_transition(ResearchState.IDEA, ResearchState.EXECUTED)

    with pytest.raises(ValueError, match="IDEA -> EXECUTED"):
        validate_transition(ResearchState.IDEA, ResearchState.EXECUTED)


def test_hypothesis_gate_requires_falsifiability_and_recorded_assumptions():
    assert check_hypothesis_gate(valid_hypothesis()).passed
    assert not check_hypothesis_gate(valid_hypothesis(predictions=[])).passed
    assert not check_hypothesis_gate(valid_hypothesis(assumptions=[])).passed
    assert not check_hypothesis_gate(
        valid_hypothesis(), fatal_critique_issues=["unresolved fatal issue"]
    ).passed


def test_experiment_gate_requires_preregistered_thresholded_protocol():
    assert check_experiment_gate(valid_experiment()).passed
    assert not check_experiment_gate(
        valid_experiment(registered_before_run=False)
    ).passed
    assert not check_experiment_gate(
        valid_experiment(success_thresholds={})
    ).passed
    assert not check_experiment_gate(valid_experiment(required_artifacts=[])).passed


def test_evidence_gate_requires_resolvable_artifacts_and_finding_source():
    evidence = Evidence(
        id="E-001",
        finding_id="FIND-001",
        artifact_ids=["ART-001"],
        direction=EvidenceDirection.SUPPORTS,
        strength=EvidenceStrength.MODERATE,
        conditions=[],
    )
    artifacts = {"ART-001": valid_artifact()}
    assert check_evidence_gate(
        evidence,
        artifacts=artifacts,
        finding_sources={"FIND-001": ["ART-001"]},
    ).passed
    assert not check_evidence_gate(
        evidence,
        artifacts={},
        finding_sources={"FIND-001": ["ART-001"]},
    ).passed
    assert not check_evidence_gate(
        evidence,
        artifacts=artifacts,
        finding_sources={},
    ).passed


def test_verification_gate_enforces_blind_independent_audit_without_p0_issues():
    verification = valid_verification()
    assert check_verification_gate(verification, producer_agent_id="C2").passed
    assert check_verification_gate(
        valid_verification(recompute_explanation=""), producer_agent_id="C2"
    ).passed
    assert not check_verification_gate(
        valid_verification(blind_initial_verdict=False), producer_agent_id="C2"
    ).passed
    assert not check_verification_gate(
        verification, producer_agent_id="D1"
    ).passed
    assert not check_verification_gate(
        valid_verification(
            issues=[
                VerificationIssue(
                    severity=IssueSeverity.P0,
                    description="raw artifact is not auditable",
                    resolved=False,
                )
            ]
        ),
        producer_agent_id="C2",
    ).passed


def test_novelty_gate_requires_search_trace_and_bounded_wording():
    report = NoveltyReport(
        claim_id="C-001",
        queries=["method A benchmark"],
        sources_checked=["https://example.org/paper"],
        closest_prior_work=["P-001"],
        differences=["different dataset"],
        status=NoveltyStatus.POSSIBLY_NOVEL,
        coverage_limits=["Only indexed English papers were searched."],
        search_date=date(2026, 8, 15),
        wording_within_coverage=True,
    )
    assert check_novelty_gate(report).passed
    assert not check_novelty_gate(report.model_copy(update={"queries": []})).passed
    assert not check_novelty_gate(
        report.model_copy(update={"closest_prior_work": [], "no_prior_work_found": False})
    ).passed
    assert not check_novelty_gate(
        report.model_copy(update={"wording_within_coverage": False})
    ).passed
    assert not check_novelty_gate(
        report.model_copy(update={"status": NoveltyStatus.UNCHECKED})
    ).passed


def test_writing_gate_rejects_orphan_or_disputed_major_claims():
    claim = Claim(
        id="C-001",
        text="A improves B in the registered benchmark.",
        scope={"benchmark": "X"},
        evidence_ids=["E-001"],
        verification_ids=["V-001"],
        status=ResearchState.VERIFIED,
    )
    draft = WritingDraft(
        major_claim_ids=["C-001"],
        referenced_claim_ids=["C-001"],
        validated_claim_ids=["C-001"],
        limitations=["Only benchmark X was tested."],
        disputed_claim_ids=[],
        writer_created_claim_ids=[],
    )
    assert check_writing_gate(draft, claims={"C-001": claim}).passed
    assert not check_writing_gate(
        draft.model_copy(update={"limitations": []}), claims={"C-001": claim}
    ).passed
    assert not check_writing_gate(
        draft.model_copy(update={"referenced_claim_ids": ["C-404"]}),
        claims={"C-001": claim},
    ).passed
    assert not check_writing_gate(
        draft.model_copy(update={"disputed_claim_ids": ["C-001"]}),
        claims={"C-001": claim},
    ).passed
