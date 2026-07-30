from agent.state import FileOperation
from tools.audit import AuditLogger
from tools.filesystem_tools import FileSystemTools
from tools.security_tools import SecurityGuard


def test_replace_requires_matching_original_hash(tmp_path, git_workspace, safety):
    guard = SecurityGuard(git_workspace, safety)
    filesystem = FileSystemTools(
        guard, lambda: "agent/001-test", AuditLogger(tmp_path / "audit.jsonl")
    )
    operation = FileOperation("replace", "README.md", "Test", "incorrect", "# Nouveau\n")
    result = filesystem.apply_operation(operation)
    assert not result.ok
    assert "hash" in (result.error or "")


def test_secret_insertion_is_refused(tmp_path, git_workspace, safety):
    guard = SecurityGuard(git_workspace, safety)
    filesystem = FileSystemTools(
        guard, lambda: "agent/001-test", AuditLogger(tmp_path / "audit.jsonl")
    )
    operation = FileOperation(
        "create", "settings.py", "Test", None, 'API_KEY = "should-not-be-written"\n'
    )
    result = filesystem.apply_operation(operation)
    assert not result.ok
    assert not (git_workspace / "settings.py").exists()
