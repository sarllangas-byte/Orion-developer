"""Contrôles de chemins, branches et types de fichiers."""

from __future__ import annotations

import os
from pathlib import Path

from agent.config import SafetyConfig


class SecurityError(PermissionError):
    """Action refusée par une règle de sécurité ORION."""


class SecurityGuard:
    def __init__(self, workspace: Path, config: SafetyConfig) -> None:
        self.workspace = workspace.resolve()
        self.config = config

    def resolve(self, relative_path: str | Path, *, for_write: bool = False) -> Path:
        raw = Path(relative_path)
        if raw.is_absolute():
            raise SecurityError("Les chemins absolus sont interdits.")
        if any(part in {"", ".", ".."} for part in raw.parts):
            raise SecurityError(f"Chemin ambigu ou traversant interdit : {relative_path}")
        target = (self.workspace / raw).resolve()
        try:
            inside = os.path.commonpath((str(self.workspace), str(target))) == str(self.workspace)
        except ValueError as exc:
            raise SecurityError("Le chemin n'appartient pas au workspace.") from exc
        if not inside:
            raise SecurityError("Accès hors workspace refusé.")
        self._reject_ignored_or_sensitive(raw)
        if for_write and target.suffix.lower() not in self.config.allowed_extensions:
            raise SecurityError(f"Extension d'écriture interdite : {target.suffix or '(aucune)'}")
        return target

    def ensure_writable_branch(self, branch: str) -> None:
        if branch in self.config.protected_branches and not self.config.allow_main_branch_write:
            raise SecurityError(f"Écriture refusée sur la branche protégée « {branch} ».")
        if not branch:
            raise SecurityError("Écriture refusée en état Git détaché.")

    def ensure_file_budget(self, paths: set[str]) -> None:
        if len(paths) > self.config.max_files_changed:
            raise SecurityError(
                f"Limite MAX_FILES_CHANGED={self.config.max_files_changed} dépassée."
            )

    def _reject_ignored_or_sensitive(self, path: Path) -> None:
        lowered_parts = [part.lower() for part in path.parts]
        ignored = {name.lower() for name in self.config.ignored_directories}
        if any(part in ignored for part in lowered_parts):
            raise SecurityError("Accès à un dossier ignoré refusé.")
        sensitive = {name.lower() for name in self.config.sensitive_names}
        for part in lowered_parts:
            stem = Path(part).stem
            if part in sensitive or stem in sensitive:
                raise SecurityError("Accès à un fichier potentiellement sensible refusé.")

    @staticmethod
    def safe_branch_name(objective_id: int) -> str:
        return f"orion/objective-{objective_id}"
