"""Append-only, provenance-aware filesystem storage for research objects.

The storage layer deliberately does not define protocol/Pydantic models.  It
accepts mappings or model-like objects exposing ``model_dump`` so the protocol
models in :mod:`research_tool.models` can be added without coupling this
foundation to their implementation.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar


class StorageError(RuntimeError):
    """Base error raised by the append-only store."""


class AlreadyExistsError(StorageError):
    """Raised when a create-only write would overwrite an existing object."""


class InvalidArtifactError(StorageError, ValueError):
    """Raised when an artifact manifest is incomplete or inconsistent."""


_T = TypeVar("_T")


def _to_jsonable(value: Any) -> Any:
    """Convert a protocol model to a JSON-compatible value without importing it."""

    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if hasattr(value, "model_dump"):
        return _to_jsonable(value.model_dump(mode="json"))
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _to_jsonable(dataclasses.asdict(value))
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted(_to_jsonable(item) for item in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"value of type {type(value).__name__} is not JSON serializable")


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize configuration deterministically for hashing and persistence."""

    return json.dumps(
        _to_jsonable(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_content(content: bytes | str | os.PathLike[str]) -> str:
    """Return the SHA-256 digest of bytes, UTF-8 text, or a file's bytes."""

    if isinstance(content, os.PathLike):
        digest = hashlib.sha256()
        with Path(content).open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    if isinstance(content, str):
        content = content.encode("utf-8")
    return sha256_bytes(content)


def sha256_config(config: Any) -> str:
    """Return the SHA-256 digest of canonical JSON configuration."""

    return sha256_bytes(canonical_json_bytes(config))


class JsonStore:
    """A project-rooted append-only JSON store.

    Each object is a separate JSON file.  Files are created through a same-
    directory temporary file followed by an atomic hard-link, which gives the
    destination create-only semantics even when two writers race.  Existing
    files are never replaced.
    """

    def __init__(self, project_dir: str | os.PathLike[str]) -> None:
        self.root = Path(project_dir).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    # Keep hashing available from the store instance as well as from the
    # module, which is convenient for service-layer adapters.
    @staticmethod
    def content_hash(content: bytes | str | os.PathLike[str]) -> str:
        return sha256_content(content)

    @staticmethod
    def config_hash(config: Any) -> str:
        return sha256_config(config)

    @staticmethod
    def _safe_component(value: str, label: str) -> str:
        if not value or value in {".", ".."} or Path(value).name != value:
            raise ValueError(f"invalid {label}: {value!r}")
        return value

    def _safe_path(self, relative_path: str | os.PathLike[str]) -> Path:
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"path must stay below project directory: {relative_path!r}")
        target = self.root / relative
        parent = target.parent.resolve()
        try:
            parent.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"path escapes project directory: {relative_path!r}") from exc
        return target

    @staticmethod
    def _atomic_create_bytes(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                # Unlike os.replace, os.link fails when the destination exists.
                os.link(temporary, path)
            except FileExistsError as exc:
                raise AlreadyExistsError(f"object already exists: {path}") from exc
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def create_bytes(self, relative_path: str | os.PathLike[str], data: bytes) -> Path:
        path = self._safe_path(relative_path)
        self._atomic_create_bytes(path, data)
        return path

    def create_json(
        self,
        collection: str | os.PathLike[str],
        identifier: str,
        payload: Any,
    ) -> Path:
        collection_path = Path(collection)
        self._safe_component(identifier, "identifier")
        return self.create_bytes(
            collection_path / f"{identifier}.json",
            canonical_json_bytes(payload) + b"\n",
        )

    # Explicit alias for callers that think in terms of records rather than files.
    create_record = create_json

    def read_bytes(self, relative_path: str | os.PathLike[str]) -> bytes:
        return self._safe_path(relative_path).read_bytes()

    def read_json(self, relative_path: str | os.PathLike[str]) -> Any:
        return json.loads(self.read_bytes(relative_path).decode("utf-8"))

    def list_json(self, collection: str | os.PathLike[str]) -> list[Any]:
        directory = self._safe_path(collection)
        if not directory.exists():
            return []
        return [self.read_json(path.relative_to(self.root)) for path in sorted(directory.glob("*.json"))]

    def create_artifact(
        self,
        manifest: Any,
        content: bytes | str | os.PathLike[str],
        *,
        config: Any = None,
    ) -> dict[str, Any]:
        """Persist raw content and its immutable manifest.

        ``manifest`` may be a future ``ArtifactManifest`` model from
        ``research_tool.models`` or a plain mapping.  The store computes and
        verifies both hashes; callers cannot provide a path outside the
        deterministic artifact directory.
        """

        payload = _to_jsonable(manifest)
        if not isinstance(payload, dict):
            raise InvalidArtifactError("artifact manifest must be a mapping")

        artifact_id = payload.get("id") or payload.get("artifact_id")
        if not isinstance(artifact_id, str):
            raise InvalidArtifactError("artifact manifest requires a string id")
        self._safe_component(artifact_id, "artifact id")

        required = ("created_by", "input_ids", "tool", "tool_version")
        missing = [field for field in required if field not in payload]
        if missing:
            raise InvalidArtifactError(f"artifact provenance missing: {', '.join(missing)}")

        if "created_at" not in payload:
            payload["created_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        if "type" not in payload:
            raise InvalidArtifactError("artifact manifest requires type")
        if not isinstance(payload["input_ids"], list):
            raise InvalidArtifactError("artifact input_ids must be a list")

        actual_content_hash = sha256_content(content)
        supplied_content_hash = payload.get("content_hash")
        if supplied_content_hash is not None and supplied_content_hash != actual_content_hash:
            raise InvalidArtifactError("content_hash does not match artifact content")
        payload["content_hash"] = actual_content_hash

        hash_config = config if config is not None else payload.pop("config", {})
        actual_config_hash = sha256_config(hash_config)
        supplied_config_hash = payload.get("config_hash")
        if supplied_config_hash is not None and supplied_config_hash != actual_config_hash:
            raise InvalidArtifactError("config_hash does not match artifact config")
        payload["config_hash"] = actual_config_hash

        content_path = Path("artifacts") / artifact_id / "content"
        manifest_path = Path("artifacts") / artifact_id / "manifest.json"
        expected_path = content_path.as_posix()
        if payload.get("path") not in (None, expected_path):
            raise InvalidArtifactError(f"artifact path must be {expected_path!r}")
        payload["path"] = expected_path

        content_bytes = Path(content).read_bytes() if isinstance(content, os.PathLike) else (
            content.encode("utf-8") if isinstance(content, str) else content
        )
        # The path-like branch was hashed from disk; all other inputs are already bytes.
        self.create_bytes(content_path, content_bytes)
        try:
            self.create_bytes(manifest_path, canonical_json_bytes(payload) + b"\n")
        except Exception:
            # The content remains immutable and is intentionally not rewritten or
            # silently replaced; a missing manifest makes the artifact incomplete.
            raise
        return payload

    put_artifact = create_artifact
    write_artifact = create_artifact

    def read_artifact_manifest(self, artifact_id: str) -> dict[str, Any]:
        self._safe_component(artifact_id, "artifact id")
        return self.read_json(Path("artifacts") / artifact_id / "manifest.json")


# Names used by adapters can remain stable while the implementation evolves.
AppendOnlyJSONStore = JsonStore


__all__ = [
    "AlreadyExistsError",
    "AppendOnlyJSONStore",
    "InvalidArtifactError",
    "JsonStore",
    "StorageError",
    "canonical_json_bytes",
    "sha256_bytes",
    "sha256_config",
    "sha256_content",
]
