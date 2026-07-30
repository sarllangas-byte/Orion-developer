"""Contrats de données échangés entre les composants d'ORION."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class MissionStatus(StrEnum):
    CREATED = "CREATED"
    ANALYZING = "ANALYZING"
    PLANNED = "PLANNED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    EXECUTING = "EXECUTING"
    TESTING = "TESTING"
    CORRECTING = "CORRECTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ApprovalDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    CANCEL = "CANCEL"


class FinalDecision(StrEnum):
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED_SAFELY = "FAILED_SAFELY"
    HUMAN_INTERVENTION_REQUIRED = "HUMAN_INTERVENTION_REQUIRED"


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
class Mission:
    objective: str
    repository: str = "workspace/geostab-demo"
    constraints: list[str] = field(default_factory=list)
    max_files_changed: int = 5
    max_iterations: int = 10
    mission_id: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    status: MissionStatus = MissionStatus.CREATED
    results: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Mission:
        objective = str(value.get("objective", "")).strip()
        if not objective:
            raise ValueError("La mission doit contenir un objectif non vide.")
        max_files = int(value.get("max_files_changed", 5))
        max_iterations = int(value.get("max_iterations", 10))
        if not 1 <= max_files <= 50 or not 1 <= max_iterations <= 50:
            raise ValueError("Les limites de mission doivent être comprises entre 1 et 50.")
        return cls(
            objective=objective,
            repository=str(value.get("repository", "workspace/geostab-demo")),
            constraints=[str(item) for item in value.get("constraints", [])],
            max_files_changed=max_files,
            max_iterations=max_iterations,
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["status"] = self.status.value
        return value


@dataclass
class RepositoryMap:
    project_type: str
    entry_points: list[str]
    test_directories: list[str]
    configuration_files: list[str]
    sensitive_files: list[str]
    candidate_files: list[str]
    risks: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Plan:
    objective: str
    understanding: str
    files_to_read: list[str]
    files_to_modify: list[str]
    files_to_create: list[str]
    implementation_steps: list[str]
    tests_to_create: list[str]
    tests_to_run: list[str]
    risks: list[str]
    rollback_strategy: str
    estimated_complexity: str
    approval_required: bool = True

    @property
    def summary(self) -> str:
        """Compatibilité avec le prototype V1."""
        return self.understanding

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Plan:
        required = ("objective", "files_to_read", "implementation_steps", "tests_to_run", "risks")
        missing = [key for key in required if key not in value]
        if missing:
            raise ValueError(f"Plan incomplet, clés manquantes : {', '.join(missing)}")
        understanding = value.get("understanding", value.get("summary"))
        if not understanding:
            raise ValueError("Plan incomplet : understanding est requis.")
        return cls(
            objective=str(value["objective"]),
            understanding=str(understanding),
            files_to_read=[str(item) for item in value["files_to_read"]],
            files_to_modify=[str(item) for item in value.get("files_to_modify", [])],
            files_to_create=[str(item) for item in value.get("files_to_create", [])],
            implementation_steps=[str(item) for item in value["implementation_steps"]],
            tests_to_create=[str(item) for item in value.get("tests_to_create", [])],
            tests_to_run=[str(item) for item in value["tests_to_run"]],
            risks=[str(item) for item in value["risks"]],
            rollback_strategy=str(
                value.get("rollback_strategy", "Restaurer les fichiers depuis leur sauvegarde.")
            ),
            estimated_complexity=str(value.get("estimated_complexity", "medium")),
            approval_required=bool(value.get("approval_required", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FileOperation:
    operation: str
    file: str
    reason: str
    original_hash: str | None
    content: str

    @property
    def path(self) -> str:
        return self.file

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> FileOperation:
        operation = str(value.get("operation", "")).lower()
        if operation not in {"create", "replace"}:
            raise ValueError("L'opération doit être create ou replace.")
        return cls(
            operation=operation,
            file=str(value["file"]),
            reason=str(value.get("reason", "")),
            original_hash=(
                str(value["original_hash"]) if value.get("original_hash") is not None else None
            ),
            content=str(value["content"]),
        )


# Nom historique conservé pour les extensions tierces.
FileChange = FileOperation


@dataclass
class RunState:
    objective_id: int
    objective: str
    task_id: int | None = None
    iteration: int = 0
    retries: int = 0
    files_changed: set[str] = field(default_factory=set)
    stopped: bool = False
    error_fingerprints: dict[str, int] = field(default_factory=dict)

    def next_iteration(self, maximum: int) -> None:
        if self.iteration >= maximum:
            raise RuntimeError(f"Limite MAX_ITERATIONS={maximum} atteinte.")
        self.iteration += 1

    def next_retry(self, maximum: int) -> None:
        if self.retries >= maximum:
            raise RuntimeError(f"Limite MAX_RETRIES_PER_TASK={maximum} atteinte.")
        self.retries += 1

    def record_error(self, fingerprint: str, maximum_identical: int) -> None:
        count = self.error_fingerprints.get(fingerprint, 0) + 1
        self.error_fingerprints[fingerprint] = count
        if count >= maximum_identical:
            raise RuntimeError(
                f"Erreur identique répétée {count} fois ; correction automatique arrêtée."
            )
