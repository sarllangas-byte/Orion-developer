from pathlib import Path

import pytest

from tools.security_tools import SecurityError, SecurityGuard


def test_refuse_path_traversal(tmp_path: Path, safety):
    guard = SecurityGuard(tmp_path, safety)
    with pytest.raises(SecurityError):
        guard.resolve("../secret.txt")


def test_refuse_absolute_path(tmp_path: Path, safety):
    guard = SecurityGuard(tmp_path, safety)
    with pytest.raises(SecurityError):
        guard.resolve((tmp_path / "file.py").resolve())


def test_refuse_sensitive_file(tmp_path: Path, safety):
    guard = SecurityGuard(tmp_path, safety)
    with pytest.raises(SecurityError):
        guard.resolve(".env")


def test_refuse_write_extension(tmp_path: Path, safety):
    guard = SecurityGuard(tmp_path, safety)
    with pytest.raises(SecurityError):
        guard.resolve("payload.exe", for_write=True)


def test_accept_safe_relative_python_path(tmp_path: Path, safety):
    guard = SecurityGuard(tmp_path, safety)
    assert guard.resolve("src/module.py") == (tmp_path / "src" / "module.py").resolve()
