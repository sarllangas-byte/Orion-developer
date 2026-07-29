from pathlib import Path

from tools.audit import AuditLogger
from tools.git_tools import GitTools
from tools.security_tools import SecurityGuard


def test_git_tool_creates_only_orion_branch(
    tmp_path: Path, git_workspace: Path, safety
):
    guard = SecurityGuard(git_workspace, safety)
    tool = GitTools(git_workspace, guard, AuditLogger(tmp_path / "audit.jsonl"))

    result = tool.create_git_branch("orion/test-git")

    assert result.ok
    assert tool.current_branch() == "orion/test-git"


def test_git_tool_rejects_arbitrary_branch_name(
    tmp_path: Path, git_workspace: Path, safety
):
    guard = SecurityGuard(git_workspace, safety)
    tool = GitTools(git_workspace, guard, AuditLogger(tmp_path / "audit.jsonl"))

    result = tool.create_git_branch("feature/not-orion")

    assert not result.ok
    assert tool.current_branch() == "main"
