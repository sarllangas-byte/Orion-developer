"""Opérations de fichiers bornées au workspace."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from collections.abc import Callable
from pathlib import Path

from agent.state import ToolResult
from tools.audit import AuditLogger
from tools.security_tools import SecurityGuard


class FileSystemTools:
    MAX_READ_BYTES = 200_000
    MAX_SEARCH_RESULTS = 200

    def __init__(
        self,
        guard: SecurityGuard,
        branch_supplier: Callable[[], str],
        audit: AuditLogger,
    ) -> None:
        self.guard = guard
        self.branch_supplier = branch_supplier
        self.audit = audit

    def list_files(self, relative_directory: str = "") -> ToolResult:
        try:
            root = (
                self.guard.workspace
                if not relative_directory
                else self.guard.resolve(relative_directory)
            )
            if not root.is_dir():
                raise FileNotFoundError(relative_directory or ".")
            files: list[str] = []
            for candidate in root.rglob("*"):
                if not candidate.is_file():
                    continue
                try:
                    relative = candidate.relative_to(self.guard.workspace)
                    self.guard.resolve(relative)
                except PermissionError:
                    continue
                files.append(relative.as_posix())
                if len(files) >= self.MAX_SEARCH_RESULTS:
                    break
            result = ToolResult(
                True,
                "list_files",
                f"{len(files)} fichier(s) listé(s).",
                {"files": files},
            )
        except Exception as exc:
            result = ToolResult(False, "list_files", "Échec du listage.", error=str(exc))
        self.audit.log("tool_call", tool="list_files", result=result.to_dict())
        return result

    def read_file(self, relative_path: str) -> ToolResult:
        try:
            target = self.guard.resolve(relative_path)
            if not target.is_file():
                raise FileNotFoundError(relative_path)
            if target.stat().st_size > self.MAX_READ_BYTES:
                raise ValueError(f"Fichier trop volumineux (>{self.MAX_READ_BYTES} octets).")
            content = target.read_text(encoding="utf-8")
            result = ToolResult(
                True,
                "read_file",
                f"{relative_path} lu.",
                {"path": relative_path, "content": content},
            )
        except Exception as exc:
            result = ToolResult(
                False,
                "read_file",
                "Lecture refusée ou impossible.",
                error=str(exc),
            )
        self.audit.log("tool_call", tool="read_file", path=relative_path, result=result.to_dict())
        return result

    def search_code(self, pattern: str) -> ToolResult:
        try:
            expression = re.compile(pattern)
            matches: list[dict[str, object]] = []
            listed = self.list_files()
            if not listed.ok:
                return listed
            for relative_path in listed.data["files"]:
                target = self.guard.resolve(str(relative_path))
                if target.stat().st_size > self.MAX_READ_BYTES:
                    continue
                try:
                    lines = target.read_text(encoding="utf-8").splitlines()
                except UnicodeDecodeError:
                    continue
                for number, line in enumerate(lines, 1):
                    if expression.search(line):
                        matches.append(
                            {"path": relative_path, "line": number, "text": line[:300]}
                        )
                        if len(matches) >= self.MAX_SEARCH_RESULTS:
                            break
                if len(matches) >= self.MAX_SEARCH_RESULTS:
                    break
            result = ToolResult(
                True,
                "search_code",
                f"{len(matches)} occurrence(s).",
                {"matches": matches},
            )
        except Exception as exc:
            result = ToolResult(False, "search_code", "Recherche impossible.", error=str(exc))
        self.audit.log("tool_call", tool="search_code", pattern=pattern, result=result.to_dict())
        return result

    def create_file(self, relative_path: str, content: str) -> ToolResult:
        return self._write(relative_path, content, must_exist=False)

    def write_file(self, relative_path: str, content: str) -> ToolResult:
        return self._write(relative_path, content, must_exist=True)

    def _write(self, relative_path: str, content: str, *, must_exist: bool) -> ToolResult:
        tool_name = "write_file" if must_exist else "create_file"
        try:
            self.guard.ensure_writable_branch(self.branch_supplier())
            target = self.guard.resolve(relative_path, for_write=True)
            if must_exist and not target.is_file():
                raise FileNotFoundError(f"Le fichier à modifier n'existe pas : {relative_path}")
            if not must_exist and target.exists():
                raise FileExistsError(f"Le fichier à créer existe déjà : {relative_path}")
            target.parent.mkdir(parents=True, exist_ok=True)
            before_hash = self.sha256(target) if target.exists() else None
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=target.parent,
                prefix=".orion-",
                suffix=".tmp",
                delete=False,
            ) as stream:
                stream.write(content)
                temporary = Path(stream.name)
            os.replace(temporary, target)
            result = ToolResult(
                True,
                tool_name,
                f"{relative_path} {'modifié' if must_exist else 'créé'}.",
                {
                    "path": relative_path,
                    "before_hash": before_hash,
                    "after_hash": self.sha256(target),
                },
            )
        except Exception as exc:
            result = ToolResult(False, tool_name, "Écriture refusée ou impossible.", error=str(exc))
        self.audit.log(
            "tool_call",
            tool=tool_name,
            path=relative_path,
            content_length=len(content),
            result=result.to_dict(),
        )
        return result

    @staticmethod
    def sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
