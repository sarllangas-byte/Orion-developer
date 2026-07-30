from pathlib import Path

from tools.audit import AuditLogger
from tools.git_tools import GitTools
from tools.security_tools import SecurityGuard


def test_git_tool_creates_only_agent_branch(tmp_path: Path, git_workspace: Path, safety):
    guard = SecurityGuard(git_workspace, safety)
    tool = GitTools(git_workspace, guard, AuditLogger(tmp_path / "audit.jsonl"))
    result = tool.create_git_branch("agent/004-test-git")
    assert result.ok
    assert tool.current_branch() == "agent/004-test-git"


def test_git_tool_rejects_arbitrary_branch_name(tmp_path: Path, git_workspace: Path, safety):
    guard = SecurityGuard(git_workspace, safety)
    tool = GitTools(git_workspace, guard, AuditLogger(tmp_path / "audit.jsonl"))
    result = tool.create_git_branch("feature/not-agent")
    assert not result.ok
    assert tool.current_branch() == "main"


def test_git_tool_refuses_dirty_repository(tmp_path: Path, git_workspace: Path, safety):
    (git_workspace / "README.md").write_text("dirty\n", encoding="utf-8")
    tool = GitTools(
        git_workspace,
        SecurityGuard(git_workspace, safety),
        AuditLogger(tmp_path / "audit.jsonl"),
    )
    result = tool.create_work_branch(4, "test")
    assert not result.ok
    assert "propre" in (result.error or "")
