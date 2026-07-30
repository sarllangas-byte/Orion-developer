from pathlib import Path

import pytest

from tools.security_tools import SecurityError, SecurityGuard


def test_refuse_path_traversal(tmp_path: Path, safety):
    guard = SecurityGuard(tmp_path, safety)
    with pytest.raises(SecurityError):
        guard.resolve("../secret.txt")


@pytest.mark.parametrize("path", ["/etc/passwd", "C:\\Windows\\system.ini", "~/secret"])
def test_refuse_absolute_paths(tmp_path: Path, safety, path: str):
    with pytest.raises(SecurityError):
        SecurityGuard(tmp_path, safety).resolve(path)


@pytest.mark.parametrize(
    "path",
    [".env", "private.pem", "private.key", "credentials.json", "secrets/value.json", ".git/config"],
)
def test_refuse_sensitive_paths(tmp_path: Path, safety, path: str):
    guard = SecurityGuard(tmp_path, safety)
    assert guard.is_sensitive_file(path)
    with pytest.raises(SecurityError):
        guard.resolve(path)


def test_refuse_write_extension(tmp_path: Path, safety):
    with pytest.raises(SecurityError):
        SecurityGuard(tmp_path, safety).resolve("payload.exe", for_write=True)


def test_accept_safe_relative_python_path(tmp_path: Path, safety):
    guard = SecurityGuard(tmp_path, safety)
    assert guard.resolve("src/module.py") == (tmp_path / "src" / "module.py").resolve()


def test_deletion_is_always_refused(tmp_path: Path, safety):
    assert not SecurityGuard(tmp_path, safety).is_delete_allowed("src/module.py")


def test_refuse_symlink_escape(tmp_path: Path, safety):
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    try:
        (workspace / "link").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Liens symboliques indisponibles.")
    with pytest.raises(SecurityError):
        SecurityGuard(workspace, safety).resolve("link/secret.py")
