"""Planificateur : recette locale vérifiable ou modèle distant JSON."""

from __future__ import annotations

from pathlib import Path

from agent.model_client import GitHubModelsClient
from agent.state import Plan


def is_rga_demo_objective(objective: str) -> bool:
    lowered = objective.lower()
    return "rga" in lowered or (
        "retrait" in lowered and "gonflement" in lowered and "argile" in lowered
    )


class Planner:
    def __init__(self, root: Path, model: GitHubModelsClient) -> None:
        self.root = root.resolve()
        self.model = model

    def create_plan(self, objective: str, files: list[str]) -> Plan:
        if is_rga_demo_objective(objective):
            return Plan(
                objective=objective,
                summary=(
                    "Ajouter un calcul pédagogique et fictif du score d'exposition RGA, "
                    "avec validation des entrées et tests unitaires."
                ),
                files_to_read=["README.md", "geostab_demo/__init__.py"],
                files_to_modify=["geostab_demo/rga.py", "tests/test_rga.py"],
                implementation_steps=[
                    "Créer une table de scores pour trois niveaux d'aléa.",
                    "Valider vulnérabilité et historique de sinistre.",
                    "Calculer un score pondéré borné entre 0 et 100.",
                    "Ajouter les cas nominaux et les erreurs d'entrée.",
                ],
                tests_to_run=["python -m pytest -q", "python -m ruff check ."],
                risks=[
                    "Formule fictive : elle ne constitue pas une conclusion géotechnique.",
                    "Les pondérations devront être validées par un expert avant tout usage réel.",
                ],
                approval_required=True,
            )
        system = (self.root / "prompts" / "system_prompt.md").read_text(encoding="utf-8")
        instruction = (self.root / "prompts" / "planner_prompt.md").read_text(encoding="utf-8")
        response = self.model.complete_json(
            system,
            instruction,
            {"objective": objective, "repository_files": files[:200]},
        )
        return Plan.from_dict(response)
