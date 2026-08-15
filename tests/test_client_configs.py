import json
import tomllib
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_codex_project_config_is_valid_and_points_to_stdio_server():
    config = tomllib.loads((ROOT / ".codex" / "config.toml").read_text())
    server = config["mcp_servers"]["research-tool"]
    assert server["command"] == "python"
    assert server["args"] == ["-m", "research_tool.mcp_server"]
    assert server["enabled"] is True


def test_json_client_configs_are_valid_and_use_same_server_entrypoint():
    configs = [
        ROOT / ".mcp.json",
        ROOT / ".kiro" / "settings" / "mcp.json",
    ]
    for path in configs:
        config = json.loads(path.read_text())
        server = config["mcpServers"]["research-tool"]
        assert server["command"] == "python"
        assert server["args"] == ["-m", "research_tool.mcp_server"]


def test_kilo_project_config_uses_local_argv_shape():
    config = json.loads((ROOT / ".kilo" / "kilo.json").read_text())
    server = config["mcp"]["research-tool"]
    assert server["type"] == "local"
    assert server["command"] == ["python", "-m", "research_tool.mcp_server"]
    assert server["enabled"] is True


def test_hermes_snippet_disables_parallel_calls_for_shared_state():
    text = (ROOT / "integrations" / "hermes.mcp.yaml").read_text()
    assert "mcp_servers:" in text
    assert "research-tool:" in text
    assert "supports_parallel_tool_calls: false" in text
