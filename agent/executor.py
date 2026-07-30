"""Conversion d'un plan approuvé en opérations de fichiers contrôlées."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.model_client import GitHubModelsClient
from agent.planner import is_rga_demo_objective
from agent.state import FileOperation, Plan, ToolResult
from tools.filesystem_tools import FileSystemTools
from tools.security_tools import SecurityGuard

RGA_MODULE = '''"""Scoring pédagogique du risque retrait-gonflement des argiles."""

from __future__ import annotations

HAZARD_SCORES = {"low": 20.0, "medium": 60.0, "high": 100.0}


def calculate_rga_exposure_score(
    hazard_level: str,
    claim_history: bool,
    vulnerability: float,
) -> float:
    """Return a fictitious exposure score from 0 to 100.

    Weights: hazard 50%, claim history 30%, vulnerability 20%.
    This is a demonstration formula, not a geotechnical diagnosis.
    """
    if not isinstance(hazard_level, str) or hazard_level.lower() not in HAZARD_SCORES:
        raise ValueError("hazard_level must be 'low', 'medium' or 'high'.")
    if not isinstance(claim_history, bool):
        raise TypeError("claim_history must be a boolean.")
    if isinstance(vulnerability, bool) or not isinstance(vulnerability, int | float):
        raise TypeError("vulnerability must be a number.")
    if not 0 <= vulnerability <= 100:
        raise ValueError("vulnerability must be between 0 and 100.")

    hazard = HAZARD_SCORES[hazard_level.lower()]
    claims = 100.0 if claim_history else 0.0
    return round(min(100.0, max(0.0, 0.50 * hazard + 0.30 * claims + 0.20 * vulnerability)), 2)
'''

RGA_TESTS = '''import pytest

from geostab.scoring import calculate_rga_exposure_score


@pytest.mark.parametrize(
    ("hazard", "claims", "vulnerability", "expected"),
    [
        ("low", False, 0, 10.0),
        ("medium", True, 50, 70.0),
        ("high", True, 100, 100.0),
    ],
)
def test_calculate_rga_exposure_score(hazard, claims, vulnerability, expected):
    assert calculate_rga_exposure_score(hazard, claims, vulnerability) == expected


def test_accepts_case_insensitive_hazard():
    assert calculate_rga_exposure_score("HIGH", False, 50) == 60.0


@pytest.mark.parametrize("hazard", ["unknown", "", None])
def test_rejects_invalid_hazard(hazard):
    with pytest.raises(ValueError):
        calculate_rga_exposure_score(hazard, False, 10)


@pytest.mark.parametrize("value", [-1, 101])
def test_rejects_out_of_range_vulnerability(value):
    with pytest.raises(ValueError):
        calculate_rga_exposure_score("medium", False, value)


def test_rejects_non_boolean_claim_history():
    with pytest.raises(TypeError):
        calculate_rga_exposure_score("medium", 1, 50)
'''


class Executor:
    def __init__(
        self,
        root: Path,
        model: GitHubModelsClient,
        filesystem: FileSystemTools,
        guard: SecurityGuard,
    ) -> None:
        self.root = root.resolve()
        self.model = model
        self.filesystem = filesystem
        self.guard = guard

    def propose_changes(self, plan: Plan) -> list[FileOperation]:
        if is_rga_demo_objective(plan.objective):
            return [
                self._operation("geostab/scoring.py", RGA_MODULE, "Ajouter le calcul RGA."),
                self._operation("tests/test_scoring.py", RGA_TESTS, "Ajouter les tests RGA."),
            ]
        context = self._read_context(plan.files_to_read)
        return self._remote_changes("coder_prompt.md", plan, context=context)

    def propose_correction(self, plan: Plan, test_output: str) -> list[FileOperation]:
        if is_rga_demo_objective(plan.objective):
            return []
        context = self._read_context(plan.files_to_modify + plan.files_to_create)
        return self._remote_changes(
            "reviewer_prompt.md",
            plan,
            context=context,
            test_output=test_output[-10_000:],
        )

    def apply_changes(
        self,
        changes: list[FileOperation],
        approved_paths: list[str],
        already_changed: set[str],
        *,
        max_files: int | None = None,
    ) -> list[ToolResult]:
        if not changes:
            return []
        approved = set(approved_paths)
        proposed = {change.file for change in changes}
        if not proposed <= approved:
            raise PermissionError(f"Changement hors plan approuvé : {sorted(proposed - approved)}")
        self.guard.ensure_file_budget(already_changed | proposed, max_files)
        results: list[ToolResult] = []
        for change in changes:
            result = self.filesystem.apply_operation(change)
            results.append(result)
            if not result.ok:
                break
            already_changed.add(change.file)
        return results

    def _operation(self, path: str, content: str, reason: str) -> FileOperation:
        target = self.guard.resolve(path, for_write=True)
        return FileOperation(
            operation="replace" if target.is_file() else "create",
            file=path,
            reason=reason,
            original_hash=self.filesystem.sha256(target) if target.is_file() else None,
            content=content,
        )

    def _read_context(self, paths: list[str]) -> dict[str, str]:
        context: dict[str, str] = {}
        for path in paths[: self.guard.config.max_files_changed]:
            result = self.filesystem.read_file(path)
            if result.ok:
                context[path] = str(result.data["content"])
        return context

    def _remote_changes(self, prompt_name: str, plan: Plan, **extra: Any) -> list[FileOperation]:
        system = (self.root / "prompts" / "system_prompt.md").read_text(encoding="utf-8")
        instruction = (self.root / "prompts" / prompt_name).read_text(encoding="utf-8")
        response = self.model.complete_json(system, instruction, {"plan": plan.to_dict(), **extra})
        raw_changes = response.get("changes")
        if not isinstance(raw_changes, list):
            raise ValueError("Réponse codeur invalide : changes doit être une liste.")
        operations: list[FileOperation] = []
        for raw in raw_changes:
            if "file" not in raw and "path" in raw:
                raw["file"] = raw.pop("path")
            target = self.guard.resolve(str(raw["file"]), for_write=True)
            if "operation" not in raw:
                raw["operation"] = "replace" if target.is_file() else "create"
            if raw["operation"] == "replace" and not raw.get("original_hash"):
                raw["original_hash"] = (
                    self.filesystem.sha256(target) if target.is_file() else None
                )
            operations.append(FileOperation.from_dict(raw))
        return operations
