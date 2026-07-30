"""Cartographie déterministe du dépôt sans lecture de secrets."""

from __future__ import annotations

from agent.state import RepositoryMap
from tools.filesystem_tools import FileSystemTools
from tools.security_tools import SecurityGuard


class RepositoryAnalyzer:
    def __init__(self, filesystem: FileSystemTools, guard: SecurityGuard) -> None:
        self.filesystem = filesystem
        self.guard = guard

    def analyze(self, objective: str) -> RepositoryMap:
        result = self.filesystem.list_files()
        if not result.ok:
            raise RuntimeError(result.error or "Cartographie impossible.")
        files = [str(item) for item in result.data["files"]]
        sensitive: list[str] = []
        ignored = {name.lower() for name in self.guard.config.ignored_directories}
        for candidate in self.guard.workspace.rglob("*"):
            if not candidate.is_file():
                continue
            relative = candidate.relative_to(self.guard.workspace).as_posix()
            if any(part.lower() in ignored for part in candidate.parts):
                continue
            if self.guard.is_sensitive_file(relative):
                sensitive.append(relative)
        safe_files = files
        project_type = self._project_type(safe_files)
        configs = [
            path
            for path in safe_files
            if path.rsplit("/", 1)[-1]
            in {"pyproject.toml", "requirements.txt", "package.json", "setup.cfg", "tox.ini"}
        ]
        tests = sorted({path.split("/", 1)[0] for path in safe_files if "test" in path.lower()})
        entry_points = [
            path
            for path in safe_files
            if path.endswith(("main.py", "__main__.py", "app.py", "index.js", "index.ts"))
        ]
        words = {word for word in objective.lower().replace("-", " ").split() if len(word) > 3}
        candidates = [
            path
            for path in safe_files
            if any(word in path.lower() for word in words)
            or path.endswith(("scoring.py", "test_scoring.py"))
        ][:30]
        risks = ["Aucun fichier sensible ne sera lu ni modifié."]
        if not tests:
            risks.append("Aucun répertoire de tests détecté.")
        return RepositoryMap(
            project_type=project_type,
            entry_points=entry_points,
            test_directories=tests,
            configuration_files=configs,
            sensitive_files=sensitive,
            candidate_files=candidates,
            risks=risks,
        )

    @staticmethod
    def _project_type(files: list[str]) -> str:
        names = {path.rsplit("/", 1)[-1] for path in files}
        if "pyproject.toml" in names or "requirements.txt" in names:
            return "python"
        if "package.json" in names:
            return "javascript/typescript"
        return "unknown"
