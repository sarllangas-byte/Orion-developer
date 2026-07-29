"""Exécution de commandes de test et lint choisies par la configuration, jamais par le modèle."""

from __future__ import annotations

import subprocess
from pathlib import Path

from agent.state import ToolResult
from tools.audit import AuditLogger


class TestTools:
    def __init__(
        self,
        workspace: Path,
        test_command: tuple[str, ...],
        lint_command: tuple[str, ...],
        audit: AuditLogger,
        timeout_seconds: int = 120,
    ) -> None:
        self.workspace = workspace.resolve()
        self.test_command = test_command
        self.lint_command = lint_command
        self.audit = audit
        self.timeout_seconds = timeout_seconds

    def run_tests(self) -> ToolResult:
        return self._run("run_tests", self.test_command)

    def run_linter(self) -> ToolResult:
        return self._run("run_linter", self.lint_command)

    def read_test_results(self, result: ToolResult) -> ToolResult:
        return ToolResult(
            result.ok,
            "read_test_results",
            "Résultat des tests analysé.",
            {
                "passed": result.ok,
                "returncode": result.data.get("returncode"),
                "output": result.data.get("output", ""),
            },
            result.error,
        )

    def _run(self, tool_name: str, command: tuple[str, ...]) -> ToolResult:
        try:
            if not command:
                raise ValueError("Commande vide interdite.")
            process = subprocess.run(
                list(command),
                cwd=self.workspace,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                timeout=self.timeout_seconds,
                check=False,
            )
            output = (process.stdout + "\n" + process.stderr).strip()
            result = ToolResult(
                process.returncode == 0,
                tool_name,
                f"Commande terminée avec le code {process.returncode}.",
                {
                    "returncode": process.returncode,
                    "output": output[-20_000:],
                    "command": list(command),
                },
                None if process.returncode == 0 else "La commande a échoué.",
            )
        except Exception as exc:
            result = ToolResult(False, tool_name, "Exécution impossible.", error=str(exc))
        self.audit.log("tool_call", tool=tool_name, result=result.to_dict())
        return result
