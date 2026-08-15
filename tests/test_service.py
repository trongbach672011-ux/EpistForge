from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from research_tool.models import (
    Claim,
    Evidence,
    EvidenceDirection,
    EvidenceStrength,
    Experiment,
    Hypothesis,
    NoveltyReport,
    NoveltyStatus,
    ResearchState,
    Verification,
    VerificationVerdict,
)
from research_tool.service import (
    GateRejected,
    PhaseViolation,
    ResearchService,
    RoleViolation,
)


def hypothesis(hypothesis_id: str = "H-001", *, author: str = "H1") -> Hypothesis:
    return Hypothesis(
        id=hypothesis_id,
        version=1,
        statement="A improves B under condition C.",
        mechanism="A changes the measured process in a testable way.",
        assumptions=["C is held constant"],
        predictions=["P-001"],
        falsifiers=["F-001"],
        required_evidence=["E-001"],
        created_by=author,
        status=ResearchState.HYPOTHESIS,
    )


def experiment() -> Experiment:
    return Experiment(
        id="EXP-001",
        hypothesis_id="H-001",
        hypothesis_version=1,
        registered_before_run=True,
        baselines=["baseline: established method"],
        controls=["control: unchanged input"],
        metrics=["accuracy"],
        success_thresholds={"accuracy": 0.9},
        failure_thresholds={"accuracy": 0.5},
        seeds=[1, 2],
        ablations=["remove A"],
        required_artifacts=["ART-001"],
        revision=0,
    )


def artifact_manifest() -> dict[str, object]:
    return {
        "id": "ART-001",
        "type": "raw_result",
        "created_by": "C2",
        "created_at": "2026-08-15T00:00:00Z",
        "input_ids": ["EXP-001"],
        "tool": "pytest-runner",
        "tool_version": "1.0",
    }


def evidence() -> Evidence:
    return Evidence(
        id="E-001",
        finding_id="FIND-001",
        artifact_ids=["ART-001"],
        direction=EvidenceDirection.SUPPORTS,
        strength=EvidenceStrength.MODERATE,
        conditions=[],
    )


def claim(*, status: ResearchState = ResearchState.VERIFIED) -> Claim:
    return Claim(
        id="C-001",
        text="A improves B in the registered benchmark.",
        scope={"benchmark": "X"},
        evidence_ids=["E-001"],
        verification_ids=["V-001"],
        status=status,
    )


def verification() -> Verification:
    return Verification(
        id="V-001",
        experiment_id="EXP-001",
        verifier="D1",
        blind_initial_verdict=True,
        recomputed_metrics={"accuracy": 0.91},
        issues=[],
        verdict=VerificationVerdict.SUPPORTED,
        spec_compliance=True,
    )


def ready_service(tmp_path: Path) -> ResearchService:
    service = ResearchService.init(tmp_path)
    service.open_hypothesis_round("R-001", ["H1"])
    service.submit_hypothesis(hypothesis(), "H1")
    service.close_hypothesis_round("R-001", "O1")
    service.register_experiment(experiment(), "D0")
    service.record_artifact(artifact_manifest(), b"accuracy=0.91\n", {"seed": 1})
    service.record_finding("FIND-001", "EXP-001", "ART-001")
    service.record_evidence(evidence(), "C2")
    return service


def test_init_status_and_hypothesis_round_are_create_only(tmp_path: Path):
    service = ResearchService.init(tmp_path)

    status = service.status()
    assert status["project_dir"] == str(tmp_path.resolve())
    assert status["counts"]["hypotheses"] == 0

    service.open_hypothesis_round("R-001", ["H1"])
    service.submit_hypothesis(hypothesis(), "H1")
    with pytest.raises(PhaseViolation):
        service.list_hypotheses("R-001")
    with pytest.raises(ValueError):
        service.open_hypothesis_round("R-001", ["H1"])

    service.close_hypothesis_round("R-001", "O1")
    listed = service.list_hypotheses("R-001")
    assert [item.id for item in listed] == ["H-001"]


def test_hypothesis_round_enforces_submitter_identity_and_peer_isolation(tmp_path: Path):
    service = ResearchService.init(tmp_path)
    service.open_hypothesis_round("R-001", ["H1", "H2"])

    with pytest.raises(RoleViolation):
        service.submit_hypothesis(hypothesis(author="H2"), "H1")
    with pytest.raises(PhaseViolation):
        service.close_hypothesis_round("R-001", "O1")

    service.submit_hypothesis(hypothesis(), "H1")
    service.submit_hypothesis(hypothesis("H-002", author="H2"), "H2")
    with pytest.raises(RoleViolation):
        service.close_hypothesis_round("R-001", "H1")
    service.close_hypothesis_round("R-001", "O1")
    assert {item.id for item in service.list_hypotheses("R-001")} == {"H-001", "H-002"}


def test_experiment_gate_and_immutable_artifact_recording(tmp_path: Path):
    service = ResearchService.init(tmp_path)
    service.open_hypothesis_round("R-001", ["H1"])
    service.submit_hypothesis(hypothesis(), "H1")
    service.close_hypothesis_round("R-001", "O1")

    with pytest.raises(GateRejected):
        service.register_experiment(
            experiment().model_copy(update={"metrics": [], "success_thresholds": {}}),
            "D0",
        )
    service.register_experiment(experiment(), "D0")
    manifest = service.record_artifact(artifact_manifest(), b"raw", {"seed": 1})
    assert manifest["content_hash"]
    with pytest.raises(ValueError):
        service.record_artifact(artifact_manifest(), b"changed", {"seed": 1})


def test_evidence_graph_and_blind_verifier_context(tmp_path: Path):
    service = ready_service(tmp_path)
    service.create_claim(claim(), "E1")
    service.submit_producer_conclusion("EXP-001", "C2", {"verdict": "supported"})

    with pytest.raises(RoleViolation):
        service.get_verifier_context("EXP-001", "C2")
    context = service.get_verifier_context("EXP-001", "D1")
    assert context["experiment"]["id"] == "EXP-001"
    assert context["artifacts"][0]["id"] == "ART-001"
    assert "producer_conclusion" not in context
    assert "supported" not in str(context)

    service.submit_verification(verification(), "C2")
    report = service.validate_completion(["C-001"], ["Only benchmark X was tested."])
    assert report["passed"] is True
    assert report["failures"] == []


def test_completion_rejects_orphan_unsupported_and_disputed_claims(tmp_path: Path):
    service = ResearchService.init(tmp_path)
    orphan = claim().model_copy(update={"evidence_ids": []})
    service.create_claim(orphan, "E1")
    report = service.validate_completion(["C-001"], ["A limitation."])
    assert report["passed"] is False
    assert any("evidence" in failure or "validated" in failure for failure in report["failures"])

    service = ready_service(tmp_path / "disputed")
    service.create_claim(claim(status=ResearchState.DISPUTED), "E1")
    report = service.validate_completion(["C-001"], ["A limitation."])
    assert report["passed"] is False
    assert any("disputed" in failure or "promotable" in failure for failure in report["failures"])


def test_evidence_and_verification_gates_reject_invalid_writes(tmp_path: Path):
    service = ready_service(tmp_path)
    with pytest.raises(GateRejected):
        service.record_evidence(
            evidence().model_copy(update={"id": "E-002", "artifact_ids": []}), "C2"
        )
    with pytest.raises(GateRejected):
        service.submit_verification(
            verification().model_copy(update={"blind_initial_verdict": False}), "C2"
        )


def test_novelty_gate_requires_search_trace_and_existing_claim(tmp_path: Path):
    service = ready_service(tmp_path)
    service.create_claim(claim(), "E1")
    report = NoveltyReport(
        claim_id="C-001",
        queries=["A B benchmark"],
        sources_checked=["https://example.org/paper"],
        closest_prior_work=["P-001"],
        differences=["different dataset"],
        status=NoveltyStatus.POSSIBLY_NOVEL,
        coverage_limits=["Only indexed English papers."],
        search_date=date(2026, 8, 15),
        wording_within_coverage=True,
    )
    service.submit_novelty(report)
    with pytest.raises(ValueError):
        service.submit_novelty(report)


def test_report_is_gate_gated_and_create_only(tmp_path: Path):
    service = ready_service(tmp_path)
    service.create_claim(claim(), "E1")
    service.submit_verification(verification(), "C2")

    result = service.generate_report(["C-001"], ["Only benchmark X was tested."])
    assert result["path"] == "reports/final_report.md"
    assert "claim_refs: [C-001]" in (tmp_path / result["path"]).read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        service.generate_report(["C-001"], ["Only benchmark X was tested."])

    incomplete = ResearchService.init(tmp_path / "incomplete")
    with pytest.raises(GateRejected):
        incomplete.generate_report([], ["No claims."])
