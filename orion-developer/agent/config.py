"""Chargement de configuration explicite, sans exécution de contenu."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SafetyConfig:
    max_iterations: int
    max_retries_per_task: int
    max_files_changed: int
    require_human_approval: bool
    allow_main_branch_write: bool
    allow_automatic_deployment: bool
    allow_file_deletion: bool
    protected_branches: tuple[str, ...]
    allowed_extensions: tuple[str, ...]
    ignored_directories: tuple[str, ...]
    sensitive_names: tuple[str, ...]


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    name: str
    endpoint: str
    timeout_seconds: int
    max_output_tokens: int
    temperature: float


@dataclass(frozen=True)
class OrionConfig:
    root: Path
    workspace: Path
    database: Path
    logs: Path
    reports: Path
    safety: SafetyConfig
    model: ModelConfig
    test_command: tuple[str, ...]
    lint_command: tuple[str, ...]


def _read_dotenv(path: Path) -> None:
    """Charge un .env local sans écraser l'environnement du processus."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip():
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _required(mapping: dict[str, Any], key: str) -> Any:
    if key not in mapping:
        raise ValueError(f"Clé de configuration manquante : {key}")
    return mapping[key]


def load_config(config_path: str | Path = "config.yaml") -> OrionConfig:
    path = Path(config_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Configuration introuvable : {path}")
    root = path.parent
    _read_dotenv(root / ".env")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("config.yaml doit contenir un objet YAML.")

    safety_raw = _required(raw, "safety")
    model_raw = _required(raw, "model")
    commands_raw = _required(raw, "commands")
    paths_raw = _required(raw, "paths")

    safety = SafetyConfig(
        max_iterations=int(_required(safety_raw, "max_iterations")),
        max_retries_per_task=int(_required(safety_raw, "max_retries_per_task")),
        max_files_changed=int(_required(safety_raw, "max_files_changed")),
        require_human_approval=bool(_required(safety_raw, "require_human_approval")),
        allow_main_branch_write=bool(_required(safety_raw, "allow_main_branch_write")),
        allow_automatic_deployment=bool(_required(safety_raw, "allow_automatic_deployment")),
        allow_file_deletion=bool(_required(safety_raw, "allow_file_deletion")),
        protected_branches=tuple(_required(safety_raw, "protected_branches")),
        allowed_extensions=tuple(_required(safety_raw, "allowed_extensions")),
        ignored_directories=tuple(_required(safety_raw, "ignored_directories")),
        sensitive_names=tuple(_required(safety_raw, "sensitive_names")),
    )
    if min(
        safety.max_iterations,
        safety.max_retries_per_task,
        safety.max_files_changed,
    ) < 1:
        raise ValueError("Les limites de sécurité doivent être supérieures ou égales à 1.")

    model = ModelConfig(
        provider=str(_required(model_raw, "provider")),
        name=os.getenv("ORION_MODEL", str(_required(model_raw, "name"))),
        endpoint=os.getenv("ORION_MODEL_ENDPOINT", str(_required(model_raw, "endpoint"))),
        timeout_seconds=int(_required(model_raw, "timeout_seconds")),
        max_output_tokens=int(_required(model_raw, "max_output_tokens")),
        temperature=float(_required(model_raw, "temperature")),
    )
    workspace_text = os.getenv("ORION_WORKSPACE", str(_required(paths_raw, "workspace")))
    workspace = Path(workspace_text)
    if not workspace.is_absolute():
        workspace = root / workspace

    def rooted(value: str) -> Path:
        candidate = Path(value)
        return candidate if candidate.is_absolute() else root / candidate

    return OrionConfig(
        root=root,
        workspace=workspace.resolve(),
        database=rooted(str(_required(paths_raw, "database"))).resolve(),
        logs=rooted(str(_required(paths_raw, "logs"))).resolve(),
        reports=rooted(str(_required(paths_raw, "reports"))).resolve(),
        safety=safety,
        model=model,
        test_command=tuple(str(part) for part in _required(commands_raw, "tests")),
        lint_command=tuple(str(part) for part in _required(commands_raw, "linter")),
    )
