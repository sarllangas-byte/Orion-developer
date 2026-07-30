"""Évaluation déterministe des tests puis audit de qualité séparé."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from agent.state import Plan, ToolResult
from tools.test_tools import TestTools


@dataclass
class Evaluation:
    passed: bool
    results: list[ToolResult]

    @property
    def tests(self) -> ToolResult:
        return self.results[0]

    @property
    def linter(self) -> ToolResult | None:
        return self.results[1] if len(self.results) > 1 else None

    @property
    def combined_output(self) -> str:
        return "\n".join(str(result.data.get("output", "")) for result in self.results)


@dataclass
class QualityEvaluation:
    objective_completed: bool
    tests_passed: bool
    security_passed: bool
    scope_respected: bool
    issues: list[str]
    recommendation: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class Evaluator:
    def __init__(self, tools: TestTools) -> None:
        self.tools = tools

    def evaluate(self) -> Evaluation:
        results = self.tools.run_detected()
        if not results:
            missing = ToolResult(False, "run_detected", "Aucun outil de test autorisé détecté.")
            return Evaluation(False, [missing])
        return Evaluation(all(result.ok for result in results), results)

    def quality_review(
        self,
        plan: Plan,
        changed_files: set[str],
        evaluation: Evaluation,
        diff: str,
    ) -> QualityEvaluation:
        approved = set(plan.files_to_modify + plan.files_to_create)
        issues: list[str] = []
        scope_respected = changed_files <= approved
        if not scope_respected:
            issues.append("Des fichiers hors plan ont été modifiés.")
        if len(diff.encode("utf-8")) > 100_000:
            issues.append("Le diff dépasse 100000 octets.")
        security_passed = not any(
            marker in diff.lower()
            for marker in ("-----begin private key-----", "credentials.json", ".env")
        )
        if not security_passed:
            issues.append("Le diff contient un marqueur potentiellement sensible.")
        objective_completed = bool(changed_files) and evaluation.passed and scope_respected
        recommendation = (
            "READY_FOR_HUMAN_REVIEW"
            if objective_completed and security_passed and not issues
            else "HUMAN_INTERVENTION_REQUIRED"
        )
        return QualityEvaluation(
            objective_completed=objective_completed,
            tests_passed=evaluation.passed,
            security_passed=security_passed,
            scope_respected=scope_respected,
            issues=issues,
            recommendation=recommendation,
        )
