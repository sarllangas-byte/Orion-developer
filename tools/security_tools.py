"""Politique de sécurité : tous les chemins restent dans le bac à sable."""

from __future__ import annotations

import os
import re
from pathlib import Path

from agent.config import SafetyConfig


class SecurityError(PermissionError):
    """Action refusée par une règle de sécurité ORION."""


class SecurityGuard:
    WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
    SECRET_PATTERNS = (
        re.compile(r"(?i)(api[_-]?key|password|secret|token)\s*[:=]\s*['\"][^'\"]+"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    )

    def __init__(self, workspace: Path, config: SafetyConfig) -> None:
        self.workspace = workspace.resolve()
        self.config = config

    def validate_path(self, relative_path: str | Path, *, for_write: bool = False) -> Path:
        return self.resolve(relative_path, for_write=for_write)

    def is_path_allowed(self, relative_path: str | Path) -> bool:
        try:
            self.resolve(relative_path)
            return True
        except (SecurityError, OSError, ValueError):
            return False

    def is_sensitive_file(self, relative_path: str | Path) -> bool:
        raw = Path(str(relative_path).replace("\\", "/"))
        lowered = [part.lower() for part in raw.parts]
        if ".git" in lowered:
            return True
        if any(part == "secrets" for part in lowered):
            return True
        filename = lowered[-1] if lowered else ""
        if filename in {".env", "credentials.json"}:
            return True
        if filename.endswith((".pem", ".key")):
            return True
        sensitive = {name.lower() for name in self.config.sensitive_names}
        return any(part in sensitive or Path(part).stem in sensitive for part in lowered)

    def is_write_allowed(self, relative_path: str | Path, branch: str) -> bool:
        try:
            self.ensure_writable_branch(branch)
            self.resolve(relative_path, for_write=True)
            return True
        except (SecurityError, OSError, ValueError):
            return False

    def is_delete_allowed(self, relative_path: str | Path) -> bool:
        del relative_path
        return False

    def resolve(self, relative_path: str | Path, *, for_write: bool = False) -> Path:
        text = str(relative_path)
        if not text or text.startswith(("~/", "~\\")) or self.WINDOWS_ABSOLUTE.match(text):
            raise SecurityError("Chemin absolu ou personnel interdit.")
        raw = Path(text)
        if raw.is_absolute() or any(part in {"", ".", ".."} for part in raw.parts):
            raise SecurityError(f"Chemin ambigu ou traversant interdit : {relative_path}")
        if self.is_sensitive_file(raw):
            raise SecurityError("Accès à un fichier sensible refusé.")
        ignored = {name.lower() for name in self.config.ignored_directories}
        if any(part.lower() in ignored for part in raw.parts):
            raise SecurityError("Accès à un dossier ignoré refusé.")
        target = (self.workspace / raw).resolve()
        try:
            inside = os.path.commonpath((str(self.workspace), str(target))) == str(self.workspace)
        except ValueError as exc:
            raise SecurityError("Le chemin n'appartient pas au workspace.") from exc
        if not inside:
            raise SecurityError("Accès hors workspace ou via lien symbolique refusé.")
        if for_write and target.suffix.lower() not in self.config.allowed_extensions:
            raise SecurityError(f"Extension d'écriture interdite : {target.suffix or '(aucune)'}")
        return target

    def ensure_writable_branch(self, branch: str) -> None:
        if branch in self.config.protected_branches and not self.config.allow_main_branch_write:
            raise SecurityError(f"Écriture refusée sur la branche protégée « {branch} ».")
        if not branch:
            raise SecurityError("Écriture refusée en état Git détaché.")
        if not branch.startswith("agent/"):
            raise SecurityError("Écriture autorisée uniquement sur une branche agent/*.")

    def ensure_file_budget(self, paths: set[str], maximum: int | None = None) -> None:
        limit = maximum or self.config.max_files_changed
        if len(paths) > limit:
            raise SecurityError(f"Limite MAX_FILES_CHANGED={limit} dépassée.")

    def validate_content(self, content: str) -> None:
        if not content.strip():
            raise SecurityError("Un fichier vide ne peut pas être écrit.")
        if len(content.encode("utf-8")) > 200_000:
            raise SecurityError("Contenu trop volumineux (>200000 octets).")
        if any(pattern.search(content) for pattern in self.SECRET_PATTERNS):
            raise SecurityError("Insertion potentielle d'un secret refusée.")

    @staticmethod
    def safe_branch_name(objective_id: int, description: str = "mission") -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", description.lower()).strip("-")[:45] or "mission"
        return f"agent/{objective_id:03d}-{slug}"
