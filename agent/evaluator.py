"""Évaluation locale déterministe."""

from __future__ import annotations

from dataclasses import dataclass

from agent.state import ToolResult
from tools.test_tools import TestTools


@dataclass
class Evaluation:
    passed: bool
    tests: ToolResult
    linter: ToolResult | None

    @property
    def combined_output(self) -> str:
        parts = [str(self.tests.data.get("output", ""))]
        if self.linter:
            parts.append(str(self.linter.data.get("output", "")))
        return "\n".join(parts)


class Evaluator:
    def __init__(self, tools: TestTools) -> None:
        self.tools = tools

    def evaluate(self) -> Evaluation:
        tests = self.tools.run_tests()
        if not tests.ok:
            return Evaluation(False, tests, None)
        linter = self.tools.run_linter()
        return Evaluation(linter.ok, tests, linter)
