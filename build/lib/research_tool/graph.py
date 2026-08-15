"""Typed evidence-graph foundation.

Protocol entities remain owned by ``research_tool.models``.  This module only
normalizes those models (or mappings) into graph records and enforces the
structural evidence chain required by SPEC.md.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from .storage import JsonStore, _to_jsonable

if TYPE_CHECKING:
    # These imports are intentionally type-only: this foundation must not
    # implement or force the protocol/Pydantic model layer before its task.
    from .models import ArtifactManifest, Claim, Evidence, Experiment, Finding


class NodeType(str, Enum):
    CLAIM = "claim"
    EVIDENCE = "evidence"
    COUNTER_EVIDENCE = "counter_evidence"
    FINDING = "finding"
    EXPERIMENT = "experiment"
    ARTIFACT = "artifact"


class EdgeType(str, Enum):
    # Canonical chain orientation: claim -> evidence -> finding -> experiment -> artifact.
    SUPPORTED_BY = "supported_by"
    COUNTERED_BY = "countered_by"
    DERIVED_FROM = "derived_from"
    PRODUCED_BY = "produced_by"
    BACKED_BY = "backed_by"
    # Evidence-graph vocabulary from the project plan, retained as typed aliases.
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    TESTED_BY = "tested_by"
    PRODUCED = "produced"


class GraphValidationError(ValueError):
    """Base error for invalid nodes, edges, or evidence chains."""


class UnknownNodeError(GraphValidationError):
    pass


class DuplicateNodeError(GraphValidationError):
    pass


class OrphanClaimError(GraphValidationError):
    """A claim has no evidence or counter-evidence attached to it."""


class IncompleteEvidenceChainError(GraphValidationError):
    """Evidence is attached to a claim but does not reach a raw artifact."""


@dataclass(frozen=True)
class GraphNode:
    id: str
    node_type: NodeType
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = dict(self.data)
        payload["id"] = self.id
        payload["node_type"] = self.node_type.value
        return payload


@dataclass(frozen=True)
class GraphEdge:
    id: str
    source_id: str
    target_id: str
    edge_type: EdgeType

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type.value,
        }


_ALLOWED_EDGES: dict[EdgeType, tuple[tuple[NodeType, NodeType], ...]] = {
    EdgeType.SUPPORTED_BY: ((NodeType.CLAIM, NodeType.EVIDENCE),),
    EdgeType.COUNTERED_BY: ((NodeType.CLAIM, NodeType.COUNTER_EVIDENCE),),
    EdgeType.DERIVED_FROM: (
        (NodeType.EVIDENCE, NodeType.FINDING),
        (NodeType.COUNTER_EVIDENCE, NodeType.FINDING),
    ),
    EdgeType.PRODUCED_BY: ((NodeType.FINDING, NodeType.EXPERIMENT),),
    EdgeType.BACKED_BY: ((NodeType.EXPERIMENT, NodeType.ARTIFACT),),
    EdgeType.SUPPORTS: ((NodeType.EVIDENCE, NodeType.CLAIM),),
    EdgeType.CONTRADICTS: (
        (NodeType.COUNTER_EVIDENCE, NodeType.CLAIM),
        (NodeType.EVIDENCE, NodeType.CLAIM),
    ),
    EdgeType.TESTED_BY: ((NodeType.FINDING, NodeType.EXPERIMENT),),
    EdgeType.PRODUCED: ((NodeType.EXPERIMENT, NodeType.ARTIFACT),),
}


def _node_type_from(value: Any, node_id: str, source: Any) -> NodeType:
    if isinstance(value, NodeType):
        return value
    if isinstance(value, str):
        try:
            return NodeType(value.lower())
        except ValueError:
            pass

    class_name = type(source).__name__.lower()
    class_name = class_name.replace("_", "")
    for candidate in NodeType:
        if candidate.value.replace("_", "") == class_name:
            return candidate

    # ID prefixes are a compatibility fallback for protocol models that do not
    # carry a graph type field.  Callers may always pass node_type explicitly.
    prefixes = (
        ("COUNTER_EVIDENCE", NodeType.COUNTER_EVIDENCE),
        ("CE-", NodeType.COUNTER_EVIDENCE),
        ("CLAIM", NodeType.CLAIM),
        ("C-", NodeType.CLAIM),
        ("EVIDENCE", NodeType.EVIDENCE),
        ("E-", NodeType.EVIDENCE),
        ("FIND", NodeType.FINDING),
        ("F-", NodeType.FINDING),
        ("EXP", NodeType.EXPERIMENT),
        ("EXPERIMENT", NodeType.EXPERIMENT),
        ("ART", NodeType.ARTIFACT),
        ("ARTIFACT", NodeType.ARTIFACT),
    )
    upper_id = node_id.upper()
    for prefix, candidate in prefixes:
        if upper_id.startswith(prefix):
            return candidate
    raise GraphValidationError(f"node {node_id!r} has no recognized node type")


def _mapping_from_model(value: Any) -> dict[str, Any]:
    payload = _to_jsonable(value)
    if not isinstance(payload, dict):
        raise GraphValidationError("graph node must be a mapping or protocol model")
    return payload


class EvidenceGraph:
    """In-memory typed graph with optional incremental filesystem persistence."""

    def __init__(self, store: JsonStore | None = None) -> None:
        self.store = store
        self.nodes: dict[str, GraphNode] = {}
        self.edges: dict[str, GraphEdge] = {}
        if store is not None:
            self._load()

    def _load(self) -> None:
        for payload in self.store.list_json("graph/nodes"):
            node = self._coerce_node(payload)
            self.nodes[node.id] = node
        for payload in self.store.list_json("graph/edges"):
            edge = GraphEdge(
                id=payload["id"],
                source_id=payload["source_id"],
                target_id=payload["target_id"],
                edge_type=EdgeType(payload["edge_type"]),
            )
            self.edges[edge.id] = edge

    @staticmethod
    def _coerce_node(node: Any, node_type: NodeType | str | None = None) -> GraphNode:
        if isinstance(node, GraphNode):
            return node
        payload = _mapping_from_model(node)
        node_id = payload.get("id")
        if not isinstance(node_id, str) or not node_id:
            raise GraphValidationError("graph node requires a non-empty string id")
        explicit_type = node_type or payload.get("node_type") or payload.get("graph_type")
        if explicit_type is None:
            candidate = payload.get("type")
            if isinstance(candidate, str) and candidate.lower() in {item.value for item in NodeType}:
                explicit_type = candidate
        resolved_type = _node_type_from(explicit_type, node_id, node)
        payload["node_type"] = resolved_type.value
        return GraphNode(id=node_id, node_type=resolved_type, data=payload)

    def add_node(self, node: Any, node_type: NodeType | str | None = None) -> GraphNode:
        record = self._coerce_node(node, node_type)
        if record.id in self.nodes:
            raise DuplicateNodeError(f"node already exists: {record.id}")
        if self.store is not None:
            self.store.create_json("graph/nodes", record.id, record.to_dict())
        self.nodes[record.id] = record
        return record

    @staticmethod
    def _coerce_edge_type(edge_type: EdgeType | str) -> EdgeType:
        if isinstance(edge_type, EdgeType):
            return edge_type
        try:
            return EdgeType(edge_type.lower())
        except (AttributeError, ValueError) as exc:
            raise GraphValidationError(f"unknown edge type: {edge_type!r}") from exc

    def _validate_edge_type(self, source_id: str, target_id: str, edge_type: EdgeType) -> None:
        source = self.nodes[source_id].node_type
        target = self.nodes[target_id].node_type
        if (source, target) not in _ALLOWED_EDGES[edge_type]:
            raise GraphValidationError(
                f"edge {edge_type.value} does not allow {source.value} -> {target.value}"
            )

    @staticmethod
    def _edge_id(source_id: str, target_id: str, edge_type: EdgeType) -> str:
        raw = json.dumps(
            {"source_id": source_id, "target_id": target_id, "edge_type": edge_type.value},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"edge-{hashlib.sha256(raw).hexdigest()}"

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType | str,
    ) -> GraphEdge:
        if source_id not in self.nodes:
            raise UnknownNodeError(f"unknown source node: {source_id}")
        if target_id not in self.nodes:
            raise UnknownNodeError(f"unknown target node: {target_id}")
        resolved_type = self._coerce_edge_type(edge_type)
        self._validate_edge_type(source_id, target_id, resolved_type)
        edge = GraphEdge(
            id=self._edge_id(source_id, target_id, resolved_type),
            source_id=source_id,
            target_id=target_id,
            edge_type=resolved_type,
        )
        if edge.id in self.edges:
            raise GraphValidationError(f"edge already exists: {edge.id}")
        if self.store is not None:
            self.store.create_json("graph/edges", edge.id, edge.to_dict())
        self.edges[edge.id] = edge
        return edge

    def edges_from(self, node_id: str, edge_type: EdgeType | str | None = None) -> list[GraphEdge]:
        resolved_type = self._coerce_edge_type(edge_type) if edge_type is not None else None
        return [
            edge
            for edge in self.edges.values()
            if edge.source_id == node_id and (resolved_type is None or edge.edge_type is resolved_type)
        ]

    def edges_to(self, node_id: str, edge_type: EdgeType | str | None = None) -> list[GraphEdge]:
        resolved_type = self._coerce_edge_type(edge_type) if edge_type is not None else None
        return [
            edge
            for edge in self.edges.values()
            if edge.target_id == node_id and (resolved_type is None or edge.edge_type is resolved_type)
        ]

    def _claim_evidence_edges(self, claim_id: str) -> list[GraphEdge]:
        result: list[GraphEdge] = []
        for edge in self.edges_from(claim_id):
            if edge.edge_type in {EdgeType.SUPPORTED_BY, EdgeType.COUNTERED_BY}:
                result.append(edge)
        # Also understand the plan's reverse vocabulary when imported graphs
        # use evidence -> claim edges.
        for edge in self.edges_to(claim_id):
            if edge.edge_type in {EdgeType.SUPPORTS, EdgeType.CONTRADICTS}:
                result.append(edge)
        return result

    def _evidence_to_finding(self, evidence_id: str) -> list[str]:
        return [
            edge.target_id
            for edge in self.edges_from(evidence_id, EdgeType.DERIVED_FROM)
            if self.nodes[edge.target_id].node_type is NodeType.FINDING
        ]

    def _finding_to_experiment(self, finding_id: str) -> list[str]:
        return [
            edge.target_id
            for edge in self.edges_from(finding_id)
            if edge.edge_type in {EdgeType.PRODUCED_BY, EdgeType.TESTED_BY}
            and self.nodes[edge.target_id].node_type is NodeType.EXPERIMENT
        ]

    def _experiment_to_artifact(self, experiment_id: str) -> list[str]:
        return [
            edge.target_id
            for edge in self.edges_from(experiment_id)
            if edge.edge_type in {EdgeType.BACKED_BY, EdgeType.PRODUCED}
            and self.nodes[edge.target_id].node_type is NodeType.ARTIFACT
        ]

    def validate_claim_chain(self, claim_id: str) -> bool:
        claim = self.nodes.get(claim_id)
        if claim is None or claim.node_type is not NodeType.CLAIM:
            raise UnknownNodeError(f"unknown claim node: {claim_id}")
        claim_edges = self._claim_evidence_edges(claim_id)
        if not claim_edges:
            raise OrphanClaimError(f"claim has no evidence: {claim_id}")
        for claim_edge in claim_edges:
            evidence_id = (
                claim_edge.target_id
                if claim_edge.source_id == claim_id
                else claim_edge.source_id
            )
            if not self._evidence_to_finding(evidence_id):
                raise IncompleteEvidenceChainError(
                    f"evidence does not point to a finding: {evidence_id}"
                )
            for finding_id in self._evidence_to_finding(evidence_id):
                experiments = self._finding_to_experiment(finding_id)
                if not experiments:
                    raise IncompleteEvidenceChainError(
                        f"finding does not point to an experiment: {finding_id}"
                    )
                if not any(self._experiment_to_artifact(exp) for exp in experiments):
                    raise IncompleteEvidenceChainError(
                        f"experiment does not point to an artifact: {experiments[0]}"
                    )
        return True

    def validate(self) -> bool:
        for edge in self.edges.values():
            if edge.source_id not in self.nodes or edge.target_id not in self.nodes:
                raise GraphValidationError(f"edge references a missing node: {edge.id}")
            self._validate_edge_type(edge.source_id, edge.target_id, edge.edge_type)
        for node in self.nodes.values():
            if node.node_type is NodeType.CLAIM:
                self.validate_claim_chain(node.id)
        return True

    def nodes_of_type(self, node_type: NodeType | str) -> list[GraphNode]:
        resolved = NodeType(node_type)
        return [node for node in self.nodes.values() if node.node_type is resolved]

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges.values()],
        }


__all__ = [
    "DuplicateNodeError",
    "EdgeType",
    "EvidenceGraph",
    "GraphEdge",
    "GraphNode",
    "GraphValidationError",
    "IncompleteEvidenceChainError",
    "NodeType",
    "OrphanClaimError",
    "UnknownNodeError",
]
