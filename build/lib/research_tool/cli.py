"""Small JSON CLI over the canonical research service."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .service import ResearchService, ServiceError


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value


class InterfaceError(ServiceError):
    """Expected CLI/MCP input error with a stable machine-readable code."""

    def __init__(self, message: str, *, code: str = "INTERFACE_ERROR") -> None:
        super().__init__(message)
        self.code = code


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InterfaceError(message, code="INVALID_ARGUMENTS")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="research-tool", description="Evidence-gated research project tool")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="initialize a local research project")
    init.add_argument("project", nargs="?", default=".")
    init.add_argument("--created-by", default="human")

    status = commands.add_parser("status", help="show project counts and graph status")
    status.add_argument("--project", required=True)

    validate = commands.add_parser("validate", help="run the completion gates")
    validate.add_argument("--project", required=True)
    validate.add_argument("--claim", dest="claims", action="append", default=[])
    validate.add_argument("--limitation", dest="limitations", action="append", default=[])

    report = commands.add_parser("report", help="write a validated final report")
    report.add_argument("--project", required=True)
    report.add_argument("--claim", dest="claims", action="append", required=True)
    report.add_argument("--limitation", dest="limitations", action="append", required=True)

    mcp = commands.add_parser("mcp", help="run the MCP stdio server")
    mcp.add_argument("--project")
    return parser


def _run(args: argparse.Namespace) -> dict[str, Any] | None:
    if args.command == "init":
        service = ResearchService.init(args.project)
        return {"project": str(service.project.store.root)}
    if args.command == "status":
        return {"status": ResearchService.open(args.project).status()}
    if args.command == "validate":
        result = ResearchService.open(args.project).validate_completion(
            args.claims, args.limitations
        )
        if not result["passed"]:
            error = InterfaceError("completion validation failed", code="VALIDATION_FAILED")
            error.result = result
            raise error
        return {"validation": result}
    if args.command == "report":
        return {"report": ResearchService.open(args.project).generate_report(args.claims, args.limitations)}
    if args.command == "mcp":
        from .mcp_server import run_stdio

        run_stdio(default_project=args.project)
        return None
    raise InterfaceError(f"unknown command: {args.command}", code="INVALID_ARGUMENTS")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        result = _run(build_parser().parse_args(argv))
        if result is not None:
            print(json.dumps({"ok": True, **_jsonable(result)}, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:  # CLI must return machine-readable failures.
        payload = {
            "ok": False,
            "error": {"code": getattr(exc, "code", "ERROR"), "message": str(exc)},
        }
        if hasattr(exc, "result"):
            payload["error"]["result"] = _jsonable(exc.result)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["InterfaceError", "build_parser", "main"]
