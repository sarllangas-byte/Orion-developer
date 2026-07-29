"""Validation humaine explicite ; aucune fusion n'est effectuée."""

from __future__ import annotations

from collections.abc import Callable


class ApprovalGate:
    def __init__(self, input_function: Callable[[str], str] = input) -> None:
        self.input_function = input_function

    def request_approval(self, stage: str, question: str) -> bool:
        answer = self.input_function(f"\n[{stage}] {question} [oui/NON] : ").strip().lower()
        return answer in {"oui", "o", "yes", "y"}
