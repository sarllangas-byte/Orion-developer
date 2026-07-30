"""Détection et exécution sans shell de commandes strictement autorisées."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
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
        allowed_commands: tuple[tuple[str, ...], ...] = (),
    ) -> None:
        self.workspace = workspace.resolve()
        self.test_command = test_command
        self.lint_command = lint_command
        self.allowed_commands = set(allowed_commands or (test_command, lint_command))
        self.audit = audit
        self.timeout_seconds = timeout_seconds

    def detect_commands(self) -> list[tuple[str, ...]]:
        commands: list[tuple[str, ...]] = []
        files = {path.name for path in self.workspace.iterdir()}
        if "pyproject.toml" in files or (self.workspace / "tests").is_dir():
            commands.extend([self.test_command, self.lint_command])
            mypy = ("python", "-m", "mypy", ".")
            pyproject = self.workspace / "pyproject.toml"
            if (
                mypy in self.allowed_commands
                and pyproject.is_file()
                and "[tool.mypy]" in pyproject.read_text(encoding="utf-8")
            ):
                commands.append(mypy)
        package = self.workspace / "package.json"
        if package.is_file():
            scripts = json.loads(package.read_text(encoding="utf-8")).get("scripts", {})
            for name in ("test", "lint", "build"):
                command = ("npm", "run", name) if name != "test" else ("npm", "test")
                if name in scripts and command in self.allowed_commands:
                    commands.append(command)
        return [
            command
            for command in commands
            if command in self.allowed_commands and command and shutil.which(command[0])
        ]

    def run_detected(self) -> list[ToolResult]:
        return [self._run("run_allowed_command", command) for command in self.detect_commands()]

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
                "exit_code": result.data.get("exit_code"),
                "stdout_summary": result.data.get("stdout_summary", ""),
                "stderr_summary": result.data.get("stderr_summary", ""),
            },
            result.error,
        )

    def _run(self, tool_name: str, command: tuple[str, ...]) -> ToolResult:
        started = time.monotonic()
        try:
            if not command or command not in self.allowed_commands:
                raise PermissionError("Commande absente de l'allowlist YAML.")
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
            duration = round(time.monotonic() - started, 3)
            stdout = process.stdout.strip()[-20_000:]
            stderr = process.stderr.strip()[-20_000:]
            result = ToolResult(
                process.returncode == 0,
                tool_name,
                f"Commande terminée avec le code {process.returncode}.",
                {
                    "command": " ".join(command),
                    "exit_code": process.returncode,
                    "duration_seconds": duration,
                    "stdout_summary": stdout,
                    "stderr_summary": stderr,
                    "status": "PASSED" if process.returncode == 0 else "FAILED",
                    # Compatibilité avec le prototype.
                    "returncode": process.returncode,
                    "output": "\n".join(part for part in (stdout, stderr) if part),
                },
                None if process.returncode == 0 else "La commande a échoué.",
            )
        except Exception as exc:
            result = ToolResult(
                False,
                tool_name,
                "Exécution impossible.",
                {
                    "command": " ".join(command),
                    "exit_code": None,
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "stdout_summary": "",
                    "stderr_summary": str(exc),
                    "status": "ERROR",
                },
                str(exc),
            )
        self.audit.log("tool_call", tool=tool_name, result=result.to_dict())
        return result
