from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from agent.config import ModelConfig, OrionConfig, SafetyConfig


@pytest.fixture
def safety() -> SafetyConfig:
    return SafetyConfig(
        max_iterations=10,
        max_retries_per_task=3,
        max_files_changed=10,
        require_human_approval=True,
        allow_main_branch_write=False,
        allow_automatic_deployment=False,
        allow_file_deletion=False,
        protected_branches=("main", "master"),
        allowed_extensions=(".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml"),
        ignored_directories=(".git", ".venv", "__pycache__", "node_modules"),
        sensitive_names=(".env", "id_rsa", "id_ed25519", "credentials", "secrets"),
    )


def git(workspace: Path, *arguments: str) -> None:
    process = subprocess.run(
        ["git", *arguments],
        cwd=workspace,
        capture_output=True,
        text=True,
        shell=False,
        check=False,
    )
    assert process.returncode == 0, process.stderr


@pytest.fixture
def git_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Démonstration\n", encoding="utf-8")
    (workspace / "geostab_demo").mkdir()
    (workspace / "geostab_demo" / "__init__.py").write_text(
        '"""Démo."""\n', encoding="utf-8"
    )
    (workspace / "tests").mkdir()
    (workspace / "tests" / "test_smoke.py").write_text(
        "def test_smoke():\n    assert True\n", encoding="utf-8"
    )
    (workspace / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n'
        '[tool.ruff]\nline-length = 100\n',
        encoding="utf-8",
    )
    git(workspace, "init", "-b", "main")
    git(workspace, "config", "user.name", "Test")
    git(workspace, "config", "user.email", "test@example.invalid")
    git(workspace, "add", ".")
    git(workspace, "commit", "-m", "Initial")
    return workspace


@pytest.fixture
def orion_config(
    tmp_path: Path, git_workspace: Path, safety: SafetyConfig
) -> OrionConfig:
    root = Path(__file__).resolve().parents[1]
    return OrionConfig(
        root=root,
        workspace=git_workspace,
        database=tmp_path / "state" / "orion.db",
        logs=tmp_path / "logs" / "orion.jsonl",
        reports=tmp_path / "reports",
        safety=safety,
        model=ModelConfig(
            provider="github_models",
            name="openai/gpt-4.1-mini",
            endpoint="https://models.github.ai/inference/chat/completions",
            timeout_seconds=1,
            max_output_tokens=1000,
            temperature=0.1,
        ),
        test_command=(sys.executable, "-m", "pytest", "-q"),
        lint_command=(sys.executable, "-m", "ruff", "check", "."),
    )
