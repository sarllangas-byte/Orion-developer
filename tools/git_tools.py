"""Sous-ensemble Git autorisé, exécuté sans shell."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from agent.state import ToolResult
from tools.audit import AuditLogger
from tools.security_tools import SecurityGuard


class GitTools:
    BRANCH_PATTERN = re.compile(r"^orion/[a-z0-9][a-z0-9._-]{0,80}$")

    def __init__(self, workspace: Path, guard: SecurityGuard, audit: AuditLogger) -> None:
        self.workspace = workspace.resolve()
        self.guard = guard
        self.audit = audit

    def _run(self, arguments: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=timeout,
            check=False,
        )

    def is_repository(self) -> bool:
        return self._run(["rev-parse", "--is-inside-work-tree"]).returncode == 0

    def current_branch(self) -> str:
        process = self._run(["branch", "--show-current"])
        return process.stdout.strip() if process.returncode == 0 else ""

    def create_git_branch(self, name: str) -> ToolResult:
        try:
            if not self.BRANCH_PATTERN.fullmatch(name):
                raise ValueError("Nom de branche refusé ; format attendu : orion/nom-court.")
            if name in self.guard.config.protected_branches:
                raise PermissionError("Impossible de créer/utiliser une branche protégée.")
            if not self.is_repository():
                raise RuntimeError("Le workspace n'est pas un dépôt Git.")
            existing = self._run(["show-ref", "--verify", "--quiet", f"refs/heads/{name}"])
            arguments = ["switch", name] if existing.returncode == 0 else ["switch", "-c", name]
            process = self._run(arguments)
            if process.returncode != 0:
                raise RuntimeError(process.stderr.strip() or "Échec de git switch.")
            result = ToolResult(
                True,
                "create_git_branch",
                f"Branche active : {name}",
                {"branch": name},
            )
        except Exception as exc:
            result = ToolResult(
                False,
                "create_git_branch",
                "Création de branche impossible.",
                error=str(exc),
            )
        self.audit.log("tool_call", tool="create_git_branch", branch=name, result=result.to_dict())
        return result

    def get_git_status(self) -> ToolResult:
        process = self._run(["status", "--short", "--branch"])
        result = ToolResult(
            process.returncode == 0,
            "get_git_status",
            "État Git lu." if process.returncode == 0 else "État Git indisponible.",
            {"output": process.stdout},
            process.stderr.strip() or None if process.returncode else None,
        )
        self.audit.log("tool_call", tool="get_git_status", result=result.to_dict())
        return result

    def show_diff(self) -> ToolResult:
        process = self._run(["diff", "--no-ext-diff", "--"])
        diff_text = process.stdout
        untracked = self._run(["ls-files", "--others", "--exclude-standard"])
        if untracked.returncode == 0:
            for relative_path in untracked.stdout.splitlines():
                try:
                    self.guard.resolve(relative_path)
                except PermissionError:
                    continue
                addition = self._run(["diff", "--no-index", "--", "/dev/null", relative_path])
                if addition.returncode in {0, 1}:
                    diff_text += addition.stdout
        result = ToolResult(
            process.returncode == 0,
            "show_diff",
            "Diff Git généré." if process.returncode == 0 else "Diff Git indisponible.",
            {"diff": diff_text},
            process.stderr.strip() or None if process.returncode else None,
        )
        self.audit.log("tool_call", tool="show_diff", result=result.to_dict())
        return result
