from __future__ import annotations

import asyncio
import json
from pathlib import Path

from research_tool.cli import main


def test_cli_init_and_status_emit_json(capsys, tmp_path: Path) -> None:
    project = tmp_path / "research-project"

    assert main(["init", str(project)]) == 0
    init_output = json.loads(capsys.readouterr().out)
    assert init_output["ok"] is True
    assert init_output["project"] == str(project.resolve())

    assert main(["status", "--project", str(project)]) == 0
    status_output = json.loads(capsys.readouterr().out)
    assert status_output["ok"] is True
    assert status_output["status"]["project"] == str(project.resolve())


def test_cli_validate_returns_nonzero_json_error_for_incomplete_project(
    capsys, tmp_path: Path
) -> None:
    project = tmp_path / "research-project"
    assert main(["init", str(project)]) == 0
    capsys.readouterr()

    assert main(["validate", "--project", str(project)]) != 0
    error_output = json.loads(capsys.readouterr().err)
    assert error_output["ok"] is False
    assert error_output["error"]["code"] == "VALIDATION_FAILED"


def test_cli_mcp_dispatches_without_opening_a_project(monkeypatch) -> None:
    import research_tool.mcp_server as mcp_server

    called: list[str | None] = []
    monkeypatch.setattr(mcp_server, "run_stdio", lambda *, default_project=None: called.append(default_project))

    assert main(["mcp"]) == 0
    assert called == [None]


def test_mcp_registers_required_tools_in_process() -> None:
    from research_tool.mcp_server import REQUIRED_TOOL_NAMES, mcp

    async def inspect_server() -> set[str]:
        try:
            from mcp.shared.memory import create_connected_server_and_client_session
        except ImportError:
            return {tool.name for tool in await mcp.list_tools()}

        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()
            response = await session.list_tools()
            return {tool.name for tool in response.tools}

    assert asyncio.run(inspect_server()) >= REQUIRED_TOOL_NAMES


def test_mcp_instructions_preserve_research_boundaries() -> None:
    from research_tool.mcp_server import mcp

    instructions = mcp.instructions or ""
    assert "evidence" in instructions.lower()
    assert "verif" in instructions.lower()
    assert "role" in instructions.lower()
