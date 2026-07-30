"""Décision humaine explicite avant toute écriture."""

from __future__ import annotations

from collections.abc import Callable

from agent.state import ApprovalDecision


class ApprovalGate:
    ALIASES = {
        "approve": ApprovalDecision.APPROVE,
        "approuver": ApprovalDecision.APPROVE,
        "oui": ApprovalDecision.APPROVE,
        "o": ApprovalDecision.APPROVE,
        "yes": ApprovalDecision.APPROVE,
        "y": ApprovalDecision.APPROVE,
        "reject": ApprovalDecision.REJECT,
        "rejeter": ApprovalDecision.REJECT,
        "non": ApprovalDecision.REJECT,
        "n": ApprovalDecision.REJECT,
        "request_changes": ApprovalDecision.REQUEST_CHANGES,
        "modifier": ApprovalDecision.REQUEST_CHANGES,
        "cancel": ApprovalDecision.CANCEL,
        "annuler": ApprovalDecision.CANCEL,
    }

    def __init__(self, input_function: Callable[[str], str] = input) -> None:
        self.input_function = input_function

    def request_decision(self, stage: str, question: str) -> ApprovalDecision:
        answer = self.input_function(
            f"\n[{stage}] {question}\n"
            "Décision [APPROVE/REJECT/REQUEST_CHANGES/CANCEL] : "
        ).strip().lower()
        return self.ALIASES.get(answer, ApprovalDecision.REJECT)

    def request_approval(self, stage: str, question: str) -> bool:
        return self.request_decision(stage, question) is ApprovalDecision.APPROVE
