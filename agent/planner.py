"""Planificateur : recette locale vérifiable ou modèle distant JSON."""

from __future__ import annotations

from pathlib import Path

from agent.model_client import GitHubModelsClient
from agent.state import Plan, RepositoryMap


def is_rga_demo_objective(objective: str) -> bool:
    lowered = objective.lower()
    return "rga" in lowered or "exposure_score" in lowered or (
        "retrait" in lowered and "gonflement" in lowered and "argile" in lowered
    )


class Planner:
    def __init__(self, root: Path, model: GitHubModelsClient) -> None:
        self.root = root.resolve()
        self.model = model

    def create_plan(
        self,
        objective: str,
        files: list[str],
        repository_map: RepositoryMap | None = None,
    ) -> Plan:
        if is_rga_demo_objective(objective):
            return Plan(
                objective=objective,
                understanding=(
                    "Ajouter au bac à sable une fonction fictive calculate_rga_exposure_score, "
                    "bornée entre 0 et 100, avec validations et tests unitaires."
                ),
                files_to_read=["README.md", "geostab/scoring.py", "tests/test_scoring.py"],
                files_to_modify=["geostab/scoring.py", "tests/test_scoring.py"],
                files_to_create=[],
                implementation_steps=[
                    "Valider le niveau d'aléa, l'historique et la vulnérabilité.",
                    "Calculer un score pondéré et le borner entre 0 et 100.",
                    "Ajouter les cas nominaux, limites et entrées invalides.",
                    "Exécuter uniquement les commandes autorisées détectées.",
                ],
                tests_to_create=["tests/test_scoring.py"],
                tests_to_run=["python -m pytest -q", "python -m ruff check ."],
                risks=[
                    "La formule est fictive et ne constitue pas un diagnostic géotechnique.",
                    "Toute utilisation réelle exige une validation métier indépendante.",
                ],
                rollback_strategy="Restaurer les sauvegardes temporaires ou git restore.",
                estimated_complexity="low",
                approval_required=True,
            )
        system = (self.root / "prompts" / "system_prompt.md").read_text(encoding="utf-8")
        instruction = (self.root / "prompts" / "planner_prompt.md").read_text(encoding="utf-8")
        response = self.model.complete_json(
            system,
            instruction,
            {
                "objective": objective,
                "repository_files": files[:200],
                "repository_map": repository_map.to_dict() if repository_map else {},
            },
        )
        return Plan.from_dict(response)
