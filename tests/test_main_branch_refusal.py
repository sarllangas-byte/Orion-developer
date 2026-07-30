from pathlib import Path

from tools.audit import AuditLogger
from tools.filesystem_tools import FileSystemTools
from tools.security_tools import SecurityGuard


def test_write_is_refused_on_main(tmp_path: Path, safety):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    guard = SecurityGuard(workspace, safety)
    tools = FileSystemTools(guard, lambda: "main", AuditLogger(tmp_path / "audit.jsonl"))
    result = tools.create_file("module.py", "VALUE = 1\n")
    assert not result.ok
    assert "branche protégée" in (result.error or "")
    assert not (workspace / "module.py").exists()
