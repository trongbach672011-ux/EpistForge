from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from research_tool.graph import (
    EdgeType,
    EvidenceGraph,
    GraphValidationError,
    NodeType,
    OrphanClaimError,
)
from research_tool.storage import AlreadyExistsError, JsonStore


def test_json_store_creates_json_once_and_never_overwrites(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)

    created = store.create_json("claims", "C-001", {"id": "C-001", "text": "first"})

    assert created == tmp_path / "claims" / "C-001.json"
    assert json.loads(created.read_text(encoding="utf-8"))["text"] == "first"
    with pytest.raises(AlreadyExistsError):
        store.create_json("claims", "C-001", {"id": "C-001", "text": "second"})
    assert json.loads(created.read_text(encoding="utf-8"))["text"] == "first"


def test_hashes_are_sha256_and_config_hash_is_canonical(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)

    assert store.content_hash(b"abc") == hashlib.sha256(b"abc").hexdigest()
    assert store.config_hash({"b": 2, "a": 1}) == store.config_hash({"a": 1, "b": 2})
    assert store.config_hash({"a": 1}) == hashlib.sha256(b'{"a":1}').hexdigest()


def test_artifact_manifest_contains_provenance_and_verified_hashes(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)

    manifest = store.create_artifact(
        {
            "id": "ART-001",
            "type": "raw_result",
            "created_by": "C2",
            "created_at": "2026-08-15T00:00:00Z",
            "input_ids": ["EXP-001"],
            "tool": "pytest",
            "tool_version": "8",
        },
        b"raw output",
        config={"seed": 7, "metric": "accuracy"},
    )

    assert manifest["content_hash"] == hashlib.sha256(b"raw output").hexdigest()
    assert manifest["config_hash"] == store.config_hash({"seed": 7, "metric": "accuracy"})
    assert manifest["path"] == "artifacts/ART-001/content"
    assert (tmp_path / manifest["path"]).read_bytes() == b"raw output"
    assert store.read_json("artifacts/ART-001/manifest.json") == manifest


def test_graph_accepts_valid_claim_evidence_experiment_artifact_chain(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)
    graph = EvidenceGraph(store)
    for node_id, node_type in (
        ("C-001", NodeType.CLAIM),
        ("E-001", NodeType.EVIDENCE),
        ("FIND-001", NodeType.FINDING),
        ("EXP-001", NodeType.EXPERIMENT),
        ("ART-001", NodeType.ARTIFACT),
    ):
        graph.add_node({"id": node_id, "node_type": node_type.value})

    graph.add_edge("C-001", "E-001", EdgeType.SUPPORTED_BY)
    graph.add_edge("E-001", "FIND-001", EdgeType.DERIVED_FROM)
    graph.add_edge("FIND-001", "EXP-001", EdgeType.PRODUCED_BY)
    graph.add_edge("EXP-001", "ART-001", EdgeType.BACKED_BY)

    assert graph.validate() is True
    assert (tmp_path / "graph" / "nodes" / "C-001.json").exists()


def test_graph_rejects_orphan_claims_and_invalid_edge_types() -> None:
    graph = EvidenceGraph()
    graph.add_node({"id": "C-001", "node_type": "claim"})

    with pytest.raises(OrphanClaimError):
        graph.validate()

    graph.add_node({"id": "ART-001", "node_type": "artifact"})
    with pytest.raises(GraphValidationError):
        graph.add_edge("C-001", "ART-001", EdgeType.SUPPORTED_BY)


def test_graph_preserves_counter_evidence_and_requires_its_artifact_chain() -> None:
    graph = EvidenceGraph()
    graph.add_node({"id": "C-001", "node_type": "claim"})
    graph.add_node({"id": "CE-001", "node_type": "counter_evidence"})
    graph.add_node({"id": "FIND-001", "node_type": "finding"})
    graph.add_node({"id": "EXP-001", "node_type": "experiment"})
    graph.add_node({"id": "ART-001", "node_type": "artifact"})

    graph.add_edge("C-001", "CE-001", EdgeType.COUNTERED_BY)
    graph.add_edge("CE-001", "FIND-001", EdgeType.DERIVED_FROM)
    graph.add_edge("FIND-001", "EXP-001", EdgeType.PRODUCED_BY)
    graph.add_edge("EXP-001", "ART-001", EdgeType.BACKED_BY)

    assert graph.validate() is True
    assert graph.edges_from("C-001")[0].edge_type is EdgeType.COUNTERED_BY
