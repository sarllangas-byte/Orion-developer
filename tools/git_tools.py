"""Sous-ensemble Git autorisé : pas de push, merge, rebase ni force-push."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from agent.state import ToolResult
from tools.audit import AuditLogger
from tools.security_tools import SecurityGuard


class GitTools:
    BRANCH_PATTERN = re.compile(r"^agent/[a-z0-9][a-z0-9._-]{0,80}$")

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

    def get_current_branch(self) -> str:
        process = self._run(["branch", "--show-current"])
        return process.stdout.strip() if process.returncode == 0 else ""

    current_branch = get_current_branch

    def is_protected_branch(self, branch: str | None = None) -> bool:
        return (branch or self.get_current_branch()) in self.guard.config.protected_branches

    def create_work_branch(self, mission_id: int, description: str) -> ToolResult:
        return self.create_git_branch(self.guard.safe_branch_name(mission_id, description))

    def create_git_branch(self, name: str) -> ToolResult:
        try:
            if not self.BRANCH_PATTERN.fullmatch(name):
                raise ValueError("Nom refusé ; format attendu : agent/004-description.")
            if not self.is_repository():
                raise RuntimeError("Le workspace n'est pas un dépôt Git.")
            dirty = self._run(["status", "--porcelain"])
            if dirty.returncode != 0 or dirty.stdout.strip():
                raise RuntimeError("Le dépôt doit être propre avant la création de branche.")
            if self.is_protected_branch(name):
                raise PermissionError("Branche protégée interdite.")
            existing = self._run(["show-ref", "--verify", "--quiet", f"refs/heads/{name}"])
            arguments = ["switch", name] if existing.returncode == 0 else ["switch", "-c", name]
            process = self._run(arguments)
            if process.returncode != 0:
                raise RuntimeError(process.stderr.strip() or "Échec de git switch.")
            result = ToolResult(
                True, "create_work_branch", f"Branche active : {name}", {"branch": name}
            )
        except Exception as exc:
            result = ToolResult(
                False, "create_work_branch", "Création de branche impossible.", error=str(exc)
            )
        self.audit.log("tool_call", tool="create_work_branch", branch=name, result=result.to_dict())
        return result

    def get_git_status(self) -> ToolResult:
        process = self._run(["status", "--short", "--branch"])
        return self._result("get_git_status", process, "État Git lu.", "output")

    def get_git_diff(self) -> ToolResult:
        process = self._run(["diff", "--no-ext-diff", "--"])
        diff_text = process.stdout
        untracked = self._run(["ls-files", "--others", "--exclude-standard"])
        if untracked.returncode == 0:
            for relative_path in untracked.stdout.splitlines():
                try:
                    self.guard.resolve(relative_path)
                except PermissionError:
                    continue
                null_device = "NUL" if os.name == "nt" else "/dev/null"
                addition = self._run(["diff", "--no-index", "--", null_device, relative_path])
                if addition.returncode in {0, 1}:
                    diff_text += addition.stdout
        result = ToolResult(
            process.returncode == 0,
            "get_git_diff",
            "Diff Git généré." if process.returncode == 0 else "Diff indisponible.",
            {"diff": diff_text},
            process.stderr.strip() or None if process.returncode else None,
        )
        self.audit.log("tool_call", tool="get_git_diff", result=result.to_dict())
        return result

    show_diff = get_git_diff

    def restore_file(self, relative_path: str) -> ToolResult:
        try:
            self.guard.resolve(relative_path, for_write=True)
            process = self._run(["restore", "--worktree", "--", relative_path])
            if process.returncode != 0:
                raise RuntimeError(process.stderr.strip() or "Restauration impossible.")
            result = ToolResult(True, "restore_file", f"{relative_path} restauré.")
        except Exception as exc:
            result = ToolResult(False, "restore_file", "Restauration refusée.", error=str(exc))
        self.audit.log(
            "tool_call", tool="restore_file", path=relative_path, result=result.to_dict()
        )
        return result

    def rollback_changes(self, paths: list[str]) -> ToolResult:
        failures = [path for path in paths if not self.restore_file(path).ok]
        return ToolResult(
            not failures,
            "rollback_changes",
            "Rollback terminé." if not failures else "Rollback incomplet.",
            {"failures": failures},
            None if not failures else "Certains fichiers n'ont pas été restaurés.",
        )

    def _result(
        self,
        tool: str,
        process: subprocess.CompletedProcess[str],
        summary: str,
        key: str,
    ) -> ToolResult:
        result = ToolResult(
            process.returncode == 0,
            tool,
            summary if process.returncode == 0 else f"{summary} Échec.",
            {key: process.stdout},
            process.stderr.strip() or None if process.returncode else None,
        )
        self.audit.log("tool_call", tool=tool, result=result.to_dict())
        return result
