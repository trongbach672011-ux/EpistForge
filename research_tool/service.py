"""Core local service for the evidence-gated research protocol.

The service is intentionally a small facade over :class:`JsonStore` and
:class:`EvidenceGraph`.  It owns workflow ordering and role boundaries; it
does not execute research or infer scientific conclusions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import date
from typing import Any, TypeVar

from pydantic import BaseModel

from .gates import (
    GateResult,
    check_evidence_gate,
    check_experiment_gate,
    check_novelty_gate,
    check_verification_gate,
    check_writing_gate,
)
from .graph import (
    EdgeType,
    EvidenceGraph,
    GraphValidationError,
    NodeType,
)
from .models import (
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
from .storage import AlreadyExistsError, JsonStore, _to_jsonable


class ServiceError(ValueError):
    """Base class for rejected service operations."""


class RoleViolation(ServiceError):
    """The caller is not allowed to perform the requested operation."""


class PhaseViolation(ServiceError):
    """The project is not in the phase required by the operation."""


class MissingObject(ServiceError):
    """A required immutable protocol object does not exist."""


class GateRejected(ServiceError):
    """A protocol gate failed before a write was attempted."""

    def __init__(self, gate: str, result: GateResult) -> None:
        self.gate = gate
        self.result = result
        super().__init__(f"{gate} rejected: {'; '.join(result.failures)}")


T = TypeVar("T", bound=BaseModel)


def _dump(value: Any) -> Any:
    """Return JSON-compatible data while preserving Pydantic enum values."""

    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return _to_jsonable(value)


def _validate_model(model_type: type[T], payload: Any) -> T:
    """Validate a JSON round-trip without weakening strict model settings.

    The protocol models intentionally reject coercion.  JSON stores enum and
    date values in their serialized form, so those values are restored to
    their declared types before strict Pydantic validation.
    """

    if isinstance(payload, model_type):
        return payload
    data = dict(payload)
    if model_type is Hypothesis:
        data["status"] = ResearchState(data["status"])
    elif model_type is Claim:
        data["status"] = ResearchState(data["status"])
    elif model_type is Evidence:
        data["direction"] = EvidenceDirection(data["direction"])
        data["strength"] = EvidenceStrength(data["strength"])
    elif model_type is Verification:
        data["verdict"] = VerificationVerdict(data["verdict"])
        data["issues"] = [
            VerificationIssue(
                severity=IssueSeverity(issue["severity"]),
                description=issue["description"],
                resolved=issue["resolved"],
            )
            for issue in data.get("issues", [])
        ]
    elif model_type is NoveltyReport:
        data["status"] = NoveltyStatus(data["status"])
        if isinstance(data.get("search_date"), str):
            data["search_date"] = date.fromisoformat(data["search_date"])
    return model_type.model_validate(data)


def _require_agent(agent_id: str, label: str = "agent_id") -> str:
    if not isinstance(agent_id, str) or not agent_id.strip():
        raise RoleViolation(f"{label} must be a non-blank string")
    return agent_id.strip()


def _gate_dict(result: GateResult) -> dict[str, Any]:
    return {"passed": result.passed, "failures": list(result.failures)}


@dataclass
class ResearchProject:
    """Opened local project state and its two source-of-truth components."""

    store: JsonStore
    graph: EvidenceGraph

    @classmethod
    def init(cls, project_dir: str | Path) -> "ResearchProject":
        store = JsonStore(project_dir)
        metadata = {"kind": "research_project", "protocol_version": "0.1"}
        try:
            store.create_json("meta", "project", metadata)
        except AlreadyExistsError:
            if store.read_json("meta/project.json") != metadata:
                raise ServiceError("project metadata does not match protocol version")
        return cls(store=store, graph=EvidenceGraph(store))

    def status(self) -> dict[str, Any]:
        return {
            "project_dir": str(self.store.root),
            "project": str(self.store.root),
            "graph": {
                "nodes": len(self.graph.nodes),
                "edges": len(self.graph.edges),
            },
            "counts": {
                "rounds": len(self.store.list_json("hypothesis_rounds")),
                "round_closures": len(self.store.list_json("hypothesis_round_closures")),
                "hypotheses": len(self.store.list_json("hypotheses")),
                "experiments": len(self.store.list_json("experiments")),
                "findings": len(self.store.list_json("findings")),
                "evidence": len(self.store.list_json("evidence")),
                "claims": len(self.store.list_json("claims")),
                "verifications": len(self.store.list_json("verifications")),
                "novelty_reports": len(self.store.list_json("novelty")),
                "producer_conclusions": len(
                    self.store.list_json("producer_conclusions")
                ),
            },
        }


class ResearchService:
    """Role- and gate-enforcing facade over one immutable local project."""

    def __init__(self, project: ResearchProject | JsonStore | str | Path) -> None:
        if isinstance(project, ResearchProject):
            self.project = project
        elif isinstance(project, JsonStore):
            self.project = ResearchProject(project, EvidenceGraph(project))
        else:
            self.project = ResearchProject.init(project)
        self.store = self.project.store
        self.graph = self.project.graph

    @classmethod
    def init(cls, project_dir: str | Path) -> "ResearchService":
        return cls(ResearchProject.init(project_dir))

    @classmethod
    def open(cls, project_dir: str | Path) -> "ResearchService":
        """Open an existing project without creating missing metadata."""
        store = JsonStore(project_dir)
        metadata_path = store.root / "meta" / "project.json"
        if not metadata_path.is_file():
            raise MissingObject(f"project is not initialized: {store.root}")
        metadata = store.read_json("meta/project.json")
        if metadata != {"kind": "research_project", "protocol_version": "0.1"}:
            raise ServiceError("project metadata does not match protocol version")
        return cls(ResearchProject(store=store, graph=EvidenceGraph(store)))

    def status(self) -> dict[str, Any]:
        return self.project.status()

    def _create_json(self, collection: str, identifier: str, payload: Any) -> None:
        try:
            self.store.create_json(collection, identifier, _dump(payload))
        except AlreadyExistsError as exc:
            raise ServiceError(f"object already exists: {collection}/{identifier}") from exc

    def _records(self, collection: str) -> list[dict[str, Any]]:
        return self.store.list_json(collection)

    def _record(self, collection: str, identifier: str) -> dict[str, Any]:
        for payload in self._records(collection):
            if payload.get("id", payload.get("round_id")) == identifier:
                return payload
            if payload.get("experiment_id") == identifier and collection in {
                "producer_conclusions",
                "novelty",
            }:
                return payload
        raise MissingObject(f"missing {collection} object: {identifier}")

    def _hypothesis_record(self, hypothesis_id: str) -> dict[str, Any]:
        return self._record("hypotheses", hypothesis_id)

    def _experiment_record(self, experiment_id: str) -> dict[str, Any]:
        return self._record("experiments", experiment_id)

    def _claim_records(self) -> dict[str, Claim]:
        return {
            payload["claim"]["id"]: _validate_model(Claim, payload["claim"])
            for payload in self._records("claims")
        }

    def _artifact_manifests(self) -> dict[str, dict[str, Any]]:
        root = self.store.root / "artifacts"
        if not root.exists():
            return {}
        manifests: dict[str, dict[str, Any]] = {}
        for directory in sorted(root.iterdir(), key=lambda item: item.name):
            path = directory / "manifest.json"
            if directory.is_dir() and path.is_file():
                payload = self.store.read_json(path.relative_to(self.store.root))
                manifests[payload["id"]] = payload
        return manifests

    @staticmethod
    def _artifact_model(payload: dict[str, Any]) -> Artifact:
        fields = set(Artifact.model_fields)
        return Artifact.model_validate({key: payload[key] for key in fields})

    def _artifact_models(self) -> dict[str, Artifact]:
        return {
            artifact_id: self._artifact_model(payload)
            for artifact_id, payload in self._artifact_manifests().items()
        }

    def _round_record(self, round_id: str) -> dict[str, Any]:
        return self._record("hypothesis_rounds", round_id)

    def _round_closed(self, round_id: str) -> bool:
        return any(
            payload.get("round_id") == round_id
            for payload in self._records("hypothesis_round_closures")
        )

    def open_hypothesis_round(
        self, round_id: str, expected_submitters: list[str] | tuple[str, ...]
    ) -> dict[str, Any]:
        if not isinstance(round_id, str) or not round_id.strip():
            raise PhaseViolation("round_id must be a non-blank string")
        submitters = sorted({_require_agent(agent, "expected_submitter") for agent in expected_submitters})
        if not submitters:
            raise PhaseViolation("at least one expected submitter is required")
        payload = {
            "round_id": round_id.strip(),
            "expected_submitters": submitters,
            "state": "OPEN",
        }
        self._create_json("hypothesis_rounds", round_id.strip(), payload)
        return payload

    def submit_hypothesis(self, hypothesis: Hypothesis, agent_id: str) -> dict[str, Any]:
        agent_id = _require_agent(agent_id)
        model = _validate_model(Hypothesis, hypothesis)
        if model.created_by != agent_id:
            raise RoleViolation("hypothesis.created_by must match agent_id")
        if model.status is not ResearchState.HYPOTHESIS:
            raise PhaseViolation("submitted hypothesis must be in HYPOTHESIS state")

        matching_rounds = []
        for round_record in self._records("hypothesis_rounds"):
            if agent_id in round_record["expected_submitters"]:
                matching_rounds.append(round_record)
        if len(matching_rounds) != 1:
            raise PhaseViolation("agent must belong to exactly one open hypothesis round")
        round_record = matching_rounds[0]
        round_id = round_record["round_id"]
        if self._round_closed(round_id):
            raise PhaseViolation(f"hypothesis round is closed: {round_id}")
        if any(
            payload.get("round_id") == round_id and payload.get("agent_id") == agent_id
            for payload in self._records("hypotheses")
        ):
            raise ServiceError(f"agent already submitted in round: {agent_id}")

        payload = {
            "id": model.id,
            "round_id": round_id,
            "agent_id": agent_id,
            "hypothesis": _dump(model),
        }
        self._create_json("hypotheses", model.id, payload)
        # The response is deliberately an acknowledgement, not peer data.
        return {"accepted": True, "hypothesis_id": model.id, "round_id": round_id}

    def close_hypothesis_round(self, round_id: str, orchestrator_id: str) -> dict[str, Any]:
        orchestrator_id = _require_agent(orchestrator_id, "orchestrator_id")
        round_record = self._round_record(round_id)
        if self._round_closed(round_id):
            raise ServiceError(f"hypothesis round already closed: {round_id}")
        if orchestrator_id in round_record["expected_submitters"]:
            raise RoleViolation("orchestrator cannot be a hypothesis submitter")
        submissions = sorted(
            payload["agent_id"]
            for payload in self._records("hypotheses")
            if payload.get("round_id") == round_id
        )
        missing = sorted(set(round_record["expected_submitters"]) - set(submissions))
        if missing:
            raise PhaseViolation(f"hypothesis round is missing submitters: {', '.join(missing)}")
        closure = {
            "round_id": round_id,
            "closed_by": orchestrator_id,
            "submitted_agents": submissions,
            "state": "CLOSED",
        }
        self._create_json("hypothesis_round_closures", round_id, closure)
        return closure

    def list_hypotheses(self, round_id: str) -> list[Hypothesis]:
        self._round_record(round_id)
        if not self._round_closed(round_id):
            raise PhaseViolation("hypotheses are hidden until the round is closed")
        records = [
            payload
            for payload in self._records("hypotheses")
            if payload.get("round_id") == round_id
        ]
        return [_validate_model(Hypothesis, payload["hypothesis"]) for payload in records]

    def register_experiment(self, experiment: Experiment, designer_id: str) -> Experiment:
        designer_id = _require_agent(designer_id, "designer_id")
        model = _validate_model(Experiment, experiment)
        result = check_experiment_gate(model)
        if not result:
            raise GateRejected("experiment", result)
        hypothesis_record = self._hypothesis_record(model.hypothesis_id)
        registered_hypothesis = _validate_model(Hypothesis, hypothesis_record["hypothesis"])
        if registered_hypothesis.version != model.hypothesis_version:
            raise PhaseViolation("experiment hypothesis version does not match the registered hypothesis")
        if registered_hypothesis.status not in {ResearchState.HYPOTHESIS, ResearchState.TESTABLE}:
            raise PhaseViolation("hypothesis is not in a testable registration state")
        if any(payload.get("experiment", {}).get("id") == model.id for payload in self._records("experiments")):
            raise ServiceError(f"experiment already exists: {model.id}")

        self.graph.add_node({"id": model.id, "node_type": NodeType.EXPERIMENT.value, **_dump(model)})
        self._create_json(
            "experiments",
            model.id,
            {"id": model.id, "designer_id": designer_id, "experiment": _dump(model)},
        )
        return model

    def record_artifact(
        self, manifest: dict[str, Any] | BaseModel, content: bytes | str | Path, config: Any = None
    ) -> dict[str, Any]:
        payload = _dump(manifest)
        if not isinstance(payload, dict):
            raise ServiceError("artifact manifest must be a mapping")
        if not payload.get("created_at"):
            raise ServiceError("artifact manifest requires deterministic created_at")
        artifact_id = payload.get("id") or payload.get("artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id.strip():
            raise ServiceError("artifact manifest requires id")
        if artifact_id in self.graph.nodes or artifact_id in self._artifact_manifests():
            raise ServiceError(f"artifact already exists: {artifact_id}")
        stored = self.store.create_artifact(payload, content, config=config)
        self.graph.add_node(
            {"id": artifact_id, "node_type": NodeType.ARTIFACT.value, **stored}
        )
        return stored

    def record_finding(self, finding_id: str, experiment_id: str, artifact_id: str) -> dict[str, Any]:
        self._experiment_record(experiment_id)
        artifacts = self._artifact_manifests()
        if artifact_id not in artifacts:
            raise MissingObject(f"missing artifact: {artifact_id}")
        experiment = _validate_model(Experiment, self._experiment_record(experiment_id)["experiment"])
        if artifact_id not in experiment.required_artifacts:
            raise PhaseViolation("finding artifact was not declared by the experiment")
        if finding_id in self.graph.nodes or any(
            payload.get("id") == finding_id for payload in self._records("findings")
        ):
            raise ServiceError(f"finding already exists: {finding_id}")

        finding = {
            "id": finding_id,
            "experiment_id": experiment_id,
            "artifact_id": artifact_id,
        }
        self.graph.add_node({"id": finding_id, "node_type": NodeType.FINDING.value, **finding})
        self.graph.add_edge(finding_id, experiment_id, EdgeType.PRODUCED_BY)
        self.graph.add_edge(experiment_id, artifact_id, EdgeType.BACKED_BY)
        self._create_json("findings", finding_id, finding)
        return finding

    def _evidence_record(self, evidence_id: str) -> dict[str, Any]:
        return self._record("evidence", evidence_id)

    def _attach_claim_evidence(self, claim_id: str, evidence_model: Evidence) -> None:
        if evidence_model.direction is EvidenceDirection.SUPPORTS:
            edge_type = EdgeType.SUPPORTED_BY
            node_type = NodeType.EVIDENCE
        else:
            edge_type = EdgeType.COUNTERED_BY
            node_type = NodeType.COUNTER_EVIDENCE
        if evidence_model.id not in self.graph.nodes:
            self.graph.add_node(
                {
                    "id": evidence_model.id,
                    "node_type": node_type.value,
                    **_dump(evidence_model),
                }
            )
        if claim_id not in self.graph.nodes:
            return
        edge_id = EvidenceGraph._edge_id(claim_id, evidence_model.id, edge_type)
        if edge_id not in self.graph.edges:
            self.graph.add_edge(claim_id, evidence_model.id, edge_type)

    def record_evidence(self, evidence: Evidence, author_id: str) -> Evidence:
        author_id = _require_agent(author_id, "author_id")
        model = _validate_model(Evidence, evidence)
        if any(payload.get("id") == model.id for payload in self._records("evidence")):
            raise ServiceError(f"evidence already exists: {model.id}")
        finding = next(
            (payload for payload in self._records("findings") if payload.get("id") == model.finding_id),
            None,
        )
        if finding is None:
            raise MissingObject(f"missing finding: {model.finding_id}")
        result = check_evidence_gate(
            model,
            artifacts=self._artifact_models(),
            finding_sources={model.finding_id: [finding["artifact_id"]]},
        )
        if not result:
            raise GateRejected("evidence", result)

        node_type = (
            NodeType.EVIDENCE
            if model.direction is EvidenceDirection.SUPPORTS
            else NodeType.COUNTER_EVIDENCE
        )
        self.graph.add_node({"id": model.id, "node_type": node_type.value, **_dump(model)})
        self.graph.add_edge(model.id, model.finding_id, EdgeType.DERIVED_FROM)
        self._create_json(
            "evidence",
            model.id,
            {"id": model.id, "author_id": author_id, "evidence": _dump(model)},
        )
        for claim_model in self._claim_records().values():
            if model.id in claim_model.evidence_ids:
                self._attach_claim_evidence(claim_model.id, model)
        return model

    def create_claim(self, claim: Claim, author_id: str) -> Claim:
        author_id = _require_agent(author_id, "author_id")
        model = _validate_model(Claim, claim)
        if any(payload.get("id") == model.id for payload in self._records("claims")):
            raise ServiceError(f"claim already exists: {model.id}")
        self.graph.add_node({"id": model.id, "node_type": NodeType.CLAIM.value, **_dump(model)})
        self._create_json(
            "claims",
            model.id,
            {"id": model.id, "author_id": author_id, "claim": _dump(model)},
        )
        for evidence_id in model.evidence_ids:
            try:
                evidence_payload = self._evidence_record(evidence_id)
            except MissingObject:
                continue
            self._attach_claim_evidence(
                model.id, _validate_model(Evidence, evidence_payload["evidence"])
            )
        return model

    def submit_producer_conclusion(
        self, experiment_id: str, producer_agent_id: str, conclusion: Any
    ) -> dict[str, Any]:
        producer_agent_id = _require_agent(producer_agent_id, "producer_agent_id")
        self._experiment_record(experiment_id)
        if any(
            payload.get("experiment_id") == experiment_id
            for payload in self._records("producer_conclusions")
        ):
            raise ServiceError(f"producer conclusion already exists: {experiment_id}")
        payload = {
            "experiment_id": experiment_id,
            "producer_agent_id": producer_agent_id,
            "conclusion": _dump(conclusion),
        }
        self._create_json("producer_conclusions", experiment_id, payload)
        return {"stored": True, "experiment_id": experiment_id}

    def _producer_ids(self, experiment_id: str) -> set[str]:
        experiment_record = self._experiment_record(experiment_id)
        experiment = _validate_model(Experiment, experiment_record["experiment"])
        producer_ids = {experiment_record["designer_id"]}
        for payload in self._records("producer_conclusions"):
            if payload.get("experiment_id") == experiment_id:
                producer_ids.add(payload["producer_agent_id"])
        for artifact_id, manifest in self._artifact_manifests().items():
            if artifact_id in experiment.required_artifacts or experiment_id in manifest.get("input_ids", []):
                producer_ids.add(manifest["created_by"])
        return producer_ids

    def get_verifier_context(self, experiment_id: str, verifier_id: str) -> dict[str, Any]:
        verifier_id = _require_agent(verifier_id, "verifier_id")
        experiment_record = self._experiment_record(experiment_id)
        if verifier_id in self._producer_ids(experiment_id):
            raise RoleViolation("producer cannot act as verifier")
        experiment = _validate_model(Experiment, experiment_record["experiment"])
        hypothesis_record = self._hypothesis_record(experiment.hypothesis_id)
        artifacts = [
            manifest
            for artifact_id, manifest in self._artifact_manifests().items()
            if artifact_id in experiment.required_artifacts
        ]
        return {
            "experiment": _dump(experiment),
            "hypothesis": hypothesis_record["hypothesis"],
            "artifacts": artifacts,
            "findings": [
                payload
                for payload in self._records("findings")
                if payload.get("experiment_id") == experiment_id
            ],
            "verifier_id": verifier_id,
        }

    def submit_verification(self, verification: Verification, producer_agent_id: str) -> Verification:
        producer_agent_id = _require_agent(producer_agent_id, "producer_agent_id")
        model = _validate_model(Verification, verification)
        self._experiment_record(model.experiment_id)
        if model.verifier in self._producer_ids(model.experiment_id):
            raise RoleViolation("producer cannot submit verification")
        result = check_verification_gate(model, producer_agent_id=producer_agent_id)
        if not result:
            raise GateRejected("verification", result)
        if any(payload.get("id") == model.id for payload in self._records("verifications")):
            raise ServiceError(f"verification already exists: {model.id}")
        self._create_json(
            "verifications",
            model.id,
            {
                "id": model.id,
                "producer_agent_id": producer_agent_id,
                "verification": _dump(model),
            },
        )
        return model

    def submit_novelty(self, report: NoveltyReport) -> NoveltyReport:
        model = _validate_model(NoveltyReport, report)
        if model.claim_id not in self._claim_records():
            raise MissingObject(f"missing claim: {model.claim_id}")
        result = check_novelty_gate(model)
        if not result:
            raise GateRejected("novelty", result)
        if any(payload.get("claim_id") == model.claim_id for payload in self._records("novelty")):
            raise ServiceError(f"novelty report already exists: {model.claim_id}")
        self._create_json("novelty", model.claim_id, model)
        return model

    def validate_completion(
        self, final_claim_ids: list[str] | tuple[str, ...], limitations: list[str] | tuple[str, ...]
    ) -> dict[str, Any]:
        claim_ids = list(dict.fromkeys(final_claim_ids))
        claims = self._claim_records()
        draft = WritingDraft(
            major_claim_ids=claim_ids,
            referenced_claim_ids=claim_ids,
            validated_claim_ids=claim_ids,
            limitations=list(limitations),
            disputed_claim_ids=[
                claim_id
                for claim_id in claim_ids
                if claim_id in claims and claims[claim_id].status is ResearchState.DISPUTED
            ],
            writer_created_claim_ids=[],
        )
        writing_result = check_writing_gate(draft, claims=claims)
        failures = list(writing_result.failures)
        if not claim_ids:
            failures.append("at least one final claim is required")
        chain_results: dict[str, dict[str, Any]] = {}
        verification_results: dict[str, dict[str, Any]] = {}
        novelty_results: dict[str, dict[str, Any]] = {}

        promotable = {
            ResearchState.VERIFIED,
            ResearchState.NOVELTY_CHECKED,
            ResearchState.PROVISIONAL_KNOWLEDGE,
        }
        for claim_id in claim_ids:
            claim_model = claims.get(claim_id)
            if claim_model is None:
                chain_results[claim_id] = {"passed": False, "failures": ["orphan claim reference"]}
                continue
            if claim_model.status is ResearchState.DISPUTED:
                failures.append(f"disputed claim cannot be finalized: {claim_id}")
            if claim_model.status not in promotable:
                failures.append(f"claim has non-promotable status: {claim_id}")
            try:
                self.graph.validate_claim_chain(claim_id)
            except GraphValidationError as exc:
                chain_results[claim_id] = {"passed": False, "failures": [str(exc)]}
                failures.append(f"invalid evidence chain for {claim_id}: {exc}")
            else:
                chain_results[claim_id] = {"passed": True, "failures": []}

            if not claim_model.verification_ids:
                failures.append(f"claim has no verification: {claim_id}")
            for verification_id in claim_model.verification_ids:
                record = next(
                    (payload for payload in self._records("verifications") if payload.get("id") == verification_id),
                    None,
                )
                if record is None:
                    verification_results[verification_id] = {
                        "passed": False,
                        "failures": ["missing verification"],
                    }
                    failures.append(f"missing verification for claim {claim_id}: {verification_id}")
                    continue
                verification_model = _validate_model(Verification, record["verification"])
                passed = verification_model.verdict is VerificationVerdict.SUPPORTED
                verification_results[verification_id] = {
                    "passed": passed,
                    "failures": [] if passed else [f"verification verdict is {verification_model.verdict.value}"],
                }
                if not passed:
                    failures.append(f"claim has unsupported verification: {claim_id}")

            if claim_model.status in {ResearchState.NOVELTY_CHECKED, ResearchState.PROVISIONAL_KNOWLEDGE}:
                novelty = next(
                    (payload for payload in self._records("novelty") if payload.get("claim_id") == claim_id),
                    None,
                )
                novelty_results[claim_id] = {
                    "passed": novelty is not None,
                    "failures": [] if novelty is not None else ["missing novelty report"],
                }
                if novelty is None:
                    failures.append(f"missing novelty report for claim {claim_id}")

        failures = list(dict.fromkeys(failures))
        return {
            "passed": not failures,
            "failures": failures,
            "final_claim_ids": claim_ids,
            "limitations": list(limitations),
            "checks": {
                "writing_gate": _gate_dict(writing_result),
                "claim_chains": chain_results,
                "verifications": verification_results,
                "novelty": novelty_results,
            },
        }

    def generate_report(
        self, final_claim_ids: list[str] | tuple[str, ...], limitations: list[str] | tuple[str, ...]
    ) -> dict[str, Any]:
        """Write a deterministic report only after the completion gate passes."""
        validation = self.validate_completion(final_claim_ids, limitations)
        if not validation["passed"]:
            raise GateRejected(
                "writing",
                GateResult(passed=False, failures=tuple(validation["failures"])),
            )

        claims = self._claim_records()
        verifications = {
            payload["id"]: _validate_model(Verification, payload["verification"])
            for payload in self._records("verifications")
        }
        novelty = {
            payload["claim_id"]: _validate_model(NoveltyReport, payload)
            for payload in self._records("novelty")
        }
        lines = [
            "# Research Report",
            "",
            "This report contains only claims that passed the completion gate.",
            "",
        ]
        for claim_id in final_claim_ids:
            claim = claims[claim_id]
            lines.extend(
                [
                    f"## {claim_id}",
                    "",
                    f"claim_refs: [{claim_id}]",
                    f"**Claim:** {claim.text}",
                    f"**Status:** `{claim.status.value}`",
                    f"**Scope:** `{_dump(claim.scope)}`",
                    f"**Evidence IDs:** {', '.join(claim.evidence_ids)}",
                    f"**Verification IDs:** {', '.join(claim.verification_ids)}",
                ]
            )
            if claim_id in novelty:
                report = novelty[claim_id]
                lines.append(f"**Novelty:** `{report.status.value}`; search date `{report.search_date.isoformat()}`")
            lines.append("")
        lines.extend(["## Limitations", ""])
        lines.extend(f"- {item}" for item in limitations)
        lines.extend(
            [
                "",
                "## Verification notes",
                "",
                "Verification IDs above refer to independently submitted verifier records.",
                "The report does not convert correlation into causation or claim universal scope.",
                "",
            ]
        )
        content = "\n".join(lines).encode("utf-8")
        try:
            path = self.store.create_bytes("reports/final_report.md", content)
        except AlreadyExistsError as exc:
            raise ServiceError("final report already exists and is immutable") from exc
        return {"path": path.relative_to(self.store.root).as_posix(), "claim_ids": list(final_claim_ids)}


__all__ = [
    "GateRejected",
    "MissingObject",
    "PhaseViolation",
    "ResearchProject",
    "ResearchService",
    "RoleViolation",
    "ServiceError",
]
