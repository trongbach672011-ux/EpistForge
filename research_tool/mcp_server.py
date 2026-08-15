"""FastMCP stdio adapter over the canonical evidence-gated service."""

from __future__ import annotations

import base64
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from .cli import InterfaceError, _jsonable
from .service import ResearchService


SERVER_INSTRUCTIONS = (
    "This server enforces an evidence-gated research protocol. Keep roles separate; "
    "consensus and confidence are not evidence. Use registered experiments, immutable "
    "artifacts, evidence chains, blind verification, novelty traces, and completion gates. "
    "Preserve failed, null, refuted, disputed, and inconclusive results."
)

mcp = FastMCP(name="research-tool", instructions=SERVER_INSTRUCTIONS)
REQUIRED_TOOL_NAMES = {
    "init", "status", "open_hypothesis_round", "submit_hypothesis",
    "close_hypothesis_round", "register_experiment", "record_artifact",
    "record_finding", "create_claim", "record_evidence", "get_verifier_context",
    "submit_verification", "submit_novelty", "validate_completion",
    "generate_report",
}
_DEFAULT_PROJECT: str | None = None


def _error(exc: Exception) -> dict[str, Any]:
    return {"ok": False, "error": {"code": getattr(exc, "code", "ERROR"), "message": str(exc)}}


def _invoke(callback: Any) -> dict[str, Any]:
    try:
        return {"ok": True, "result": _jsonable(callback())}
    except Exception as exc:
        return _error(exc)


def _project_path(project: str | None) -> str:
    path = project or _DEFAULT_PROJECT or os.environ.get("RESEARCH_TOOL_PROJECT")
    if not path:
        raise InterfaceError("project is required", code="INVALID_INPUT")
    return path


def _service(project: str | None) -> ResearchService:
    return ResearchService.open(_project_path(project))


@mcp.tool()
def init(project: str) -> dict[str, Any]:
    """Initialize a project directory."""
    return _invoke(lambda: {"project": str(ResearchService.init(project).project.store.root)})


@mcp.tool()
def status(project: str | None = None) -> dict[str, Any]:
    """Read project counts and graph status."""
    return _invoke(lambda: _service(project).status())


@mcp.tool()
def open_hypothesis_round(project: str | None, round_id: str, expected_submitters: list[str]) -> dict[str, Any]:
    """Open an independent round before peer hypotheses become visible."""
    return _invoke(lambda: _service(project).open_hypothesis_round(round_id, expected_submitters))


@mcp.tool()
def submit_hypothesis(project: str | None, hypothesis: dict[str, Any], agent_id: str) -> dict[str, Any]:
    """Submit one falsifiable hypothesis while peer isolation is active."""
    return _invoke(lambda: _service(project).submit_hypothesis(hypothesis, agent_id))


@mcp.tool()
def close_hypothesis_round(project: str | None, round_id: str, orchestrator_id: str) -> dict[str, Any]:
    """Close a round only after every expected submitter has submitted."""
    return _invoke(lambda: _service(project).close_hypothesis_round(round_id, orchestrator_id))


@mcp.tool()
def register_experiment(project: str | None, experiment: dict[str, Any], designer_id: str) -> dict[str, Any]:
    """Pre-register baselines, controls, metrics, thresholds, seeds, and artifacts."""
    return _invoke(lambda: _service(project).register_experiment(experiment, designer_id))


@mcp.tool()
def record_artifact(project: str | None, manifest: dict[str, Any], content: str, config: dict[str, Any] | None = None, content_encoding: str = "utf-8") -> dict[str, Any]:
    """Persist an immutable raw artifact; base64 is available for binary content."""
    def call() -> Any:
        raw: bytes | str = content
        if content_encoding == "base64":
            raw = base64.b64decode(content, validate=True)
        elif content_encoding != "utf-8":
            raise InterfaceError("content_encoding must be utf-8 or base64", code="INVALID_INPUT")
        return _service(project).record_artifact(manifest, raw, config)
    return _invoke(call)


@mcp.tool()
def record_finding(project: str | None, finding_id: str, experiment_id: str, artifact_id: str) -> dict[str, Any]:
    """Link a finding to a registered experiment and declared artifact."""
    return _invoke(lambda: _service(project).record_finding(finding_id, experiment_id, artifact_id))


@mcp.tool()
def create_claim(project: str | None, claim: dict[str, Any], author_id: str) -> dict[str, Any]:
    """Create a scoped claim; finalization still requires all gates."""
    return _invoke(lambda: _service(project).create_claim(claim, author_id))


@mcp.tool()
def record_evidence(project: str | None, evidence: dict[str, Any], author_id: str) -> dict[str, Any]:
    """Record supporting or contradicting evidence without deleting negatives."""
    return _invoke(lambda: _service(project).record_evidence(evidence, author_id))


@mcp.tool()
def get_verifier_context(project: str | None, experiment_id: str, verifier_id: str) -> dict[str, Any]:
    """Return blind inputs without producer conclusions or prior verdicts."""
    return _invoke(lambda: _service(project).get_verifier_context(experiment_id, verifier_id))


@mcp.tool()
def submit_verification(project: str | None, verification: dict[str, Any], producer_agent_id: str) -> dict[str, Any]:
    """Submit an independent verification subject to the verification gate."""
    return _invoke(lambda: _service(project).submit_verification(verification, producer_agent_id))


@mcp.tool()
def submit_novelty(project: str | None, novelty: dict[str, Any]) -> dict[str, Any]:
    """Record a bounded novelty search separately from correctness."""
    return _invoke(lambda: _service(project).submit_novelty(novelty))


@mcp.tool()
def validate_completion(project: str | None, final_claim_ids: list[str], limitations: list[str]) -> dict[str, Any]:
    """Run graph, evidence, verification, novelty, and writing gates."""
    return _invoke(lambda: _service(project).validate_completion(final_claim_ids, limitations))


@mcp.tool()
def generate_report(project: str | None, final_claim_ids: list[str], limitations: list[str]) -> dict[str, Any]:
    """Generate a deterministic report only from claims that passed all gates."""
    return _invoke(lambda: _service(project).generate_report(final_claim_ids, limitations))


def run_stdio(*, default_project: str | None = None) -> None:
    global _DEFAULT_PROJECT
    _DEFAULT_PROJECT = default_project
    mcp.run(transport="stdio")


def main() -> None:
    run_stdio()


if __name__ == "__main__":
    main()


__all__ = ["REQUIRED_TOOL_NAMES", "SERVER_INSTRUCTIONS", "main", "mcp", "run_stdio"]
