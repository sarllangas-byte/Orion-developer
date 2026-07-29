"""Objets d'état sérialisables échangés entre les composants."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ToolResult:
    ok: bool
    tool: str
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Plan:
    objective: str
    summary: str
    files_to_read: list[str]
    files_to_modify: list[str]
    implementation_steps: list[str]
    tests_to_run: list[str]
    risks: list[str]
    approval_required: bool = True

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Plan:
        required = (
            "objective",
            "summary",
            "files_to_read",
            "files_to_modify",
            "implementation_steps",
            "tests_to_run",
            "risks",
        )
        missing = [key for key in required if key not in value]
        if missing:
            raise ValueError(f"Plan incomplet, clés manquantes : {', '.join(missing)}")
        return cls(
            objective=str(value["objective"]),
            summary=str(value["summary"]),
            files_to_read=[str(item) for item in value["files_to_read"]],
            files_to_modify=[str(item) for item in value["files_to_modify"]],
            implementation_steps=[str(item) for item in value["implementation_steps"]],
            tests_to_run=[str(item) for item in value["tests_to_run"]],
            risks=[str(item) for item in value["risks"]],
            approval_required=bool(value.get("approval_required", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FileChange:
    path: str
    content: str
    reason: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> FileChange:
        return cls(
            path=str(value["path"]),
            content=str(value["content"]),
            reason=str(value.get("reason", "")),
        )


@dataclass
class RunState:
    objective_id: int
    objective: str
    task_id: int | None = None
    iteration: int = 0
    retries: int = 0
    files_changed: set[str] = field(default_factory=set)
    stopped: bool = False

    def next_iteration(self, maximum: int) -> None:
        if self.iteration >= maximum:
            raise RuntimeError(f"Limite MAX_ITERATIONS={maximum} atteinte.")
        self.iteration += 1

    def next_retry(self, maximum: int) -> None:
        if self.retries >= maximum:
            raise RuntimeError(f"Limite MAX_RETRIES_PER_TASK={maximum} atteinte.")
        self.retries += 1
