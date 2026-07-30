"""Fonctions explicites demandées par la politique ORION."""

from pathlib import Path

from tools.security_tools import SecurityGuard


def validate_path(guard: SecurityGuard, path: str | Path, *, for_write: bool = False) -> Path:
    return guard.validate_path(path, for_write=for_write)


def is_path_allowed(guard: SecurityGuard, path: str | Path) -> bool:
    return guard.is_path_allowed(path)


def is_sensitive_file(guard: SecurityGuard, path: str | Path) -> bool:
    return guard.is_sensitive_file(path)


def is_write_allowed(guard: SecurityGuard, path: str | Path, branch: str) -> bool:
    return guard.is_write_allowed(path, branch)


def is_delete_allowed(guard: SecurityGuard, path: str | Path) -> bool:
    return guard.is_delete_allowed(path)
