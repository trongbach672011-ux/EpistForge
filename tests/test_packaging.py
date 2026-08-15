from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_console_script_and_one_command_install_docs_are_present():
    pyproject = (ROOT / "pyproject.toml").read_text()
    readme = (ROOT / "README.md").read_text()
    docs = (ROOT / "docs" / "integrations.md").read_text()

    assert 'research-tool = "research_tool.cli:main"' in pyproject
    assert "uvx --from . research-tool --help" in readme
    assert "uv tool install ." in readme
    assert "uvx --from . research-tool --help" in docs
