"""Conversion d'un plan approuvé en changements de fichiers contrôlés."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.model_client import GitHubModelsClient
from agent.planner import is_rga_demo_objective
from agent.state import FileChange, Plan, ToolResult
from tools.filesystem_tools import FileSystemTools
from tools.security_tools import SecurityGuard

RGA_MODULE = '''"""Calcul pédagogique d'un score RGA fictif.

Ce module n'est pas un diagnostic et ses pondérations doivent être validées par un expert.
"""

from __future__ import annotations

ALEA_SCORES = {"faible": 20.0, "moyen": 60.0, "fort": 100.0}


def calculer_score_exposition_rga(
    niveau_alea: str,
    historique_sinistre: bool,
    vulnerabilite_batiment: float,
) -> float:
    """Retourne un score fictif de 0 à 100 à partir de trois facteurs.

    Pondérations : aléa 50 %, historique 30 %, vulnérabilité 20 %.
    """
    if not isinstance(niveau_alea, str) or niveau_alea.lower() not in ALEA_SCORES:
        raise ValueError("niveau_alea doit être 'faible', 'moyen' ou 'fort'.")
    if not isinstance(historique_sinistre, bool):
        raise TypeError("historique_sinistre doit être un booléen.")
    if isinstance(vulnerabilite_batiment, bool) or not isinstance(
        vulnerabilite_batiment, int | float
    ):
        raise TypeError("vulnerabilite_batiment doit être un nombre.")
    if not 0 <= vulnerabilite_batiment <= 100:
        raise ValueError("vulnerabilite_batiment doit être comprise entre 0 et 100.")

    alea = ALEA_SCORES[niveau_alea.lower()]
    historique = 100.0 if historique_sinistre else 0.0
    score = 0.50 * alea + 0.30 * historique + 0.20 * vulnerabilite_batiment
    return round(score, 2)
'''

RGA_TESTS = '''import pytest

from geostab_demo.rga import calculer_score_exposition_rga


@pytest.mark.parametrize(
    ("alea", "historique", "vulnerabilite", "attendu"),
    [
        ("faible", False, 0, 10.0),
        ("moyen", True, 50, 70.0),
        ("fort", True, 100, 100.0),
    ],
)
def test_calculer_score_exposition_rga(alea, historique, vulnerabilite, attendu):
    assert calculer_score_exposition_rga(alea, historique, vulnerabilite) == attendu


def test_accepte_la_casse_du_niveau_alea():
    assert calculer_score_exposition_rga("FORT", False, 50) == 60.0


@pytest.mark.parametrize("niveau", ["inconnu", "", None])
def test_refuse_un_niveau_alea_invalide(niveau):
    with pytest.raises(ValueError):
        calculer_score_exposition_rga(niveau, False, 10)


@pytest.mark.parametrize("valeur", [-1, 101])
def test_refuse_une_vulnerabilite_hors_limites(valeur):
    with pytest.raises(ValueError):
        calculer_score_exposition_rga("moyen", False, valeur)


def test_refuse_un_historique_non_booleen():
    with pytest.raises(TypeError):
        calculer_score_exposition_rga("moyen", 1, 50)
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

    def propose_changes(self, plan: Plan) -> list[FileChange]:
        if is_rga_demo_objective(plan.objective):
            return [
                FileChange("geostab_demo/rga.py", RGA_MODULE, "Ajouter le calcul RGA fictif."),
                FileChange("tests/test_rga.py", RGA_TESTS, "Tester calcul et validation."),
            ]
        context = self._read_context(plan.files_to_read)
        return self._remote_changes("coder_prompt.md", plan, context=context)

    def propose_correction(self, plan: Plan, test_output: str) -> list[FileChange]:
        if is_rga_demo_objective(plan.objective):
            return []
        context = self._read_context(plan.files_to_modify)
        return self._remote_changes(
            "reviewer_prompt.md",
            plan,
            context=context,
            test_output=test_output[-10_000:],
        )

    def apply_changes(
        self, changes: list[FileChange], approved_paths: list[str], already_changed: set[str]
    ) -> list[ToolResult]:
        if not changes:
            return []
        approved = set(approved_paths)
        proposed = {change.path for change in changes}
        if not proposed <= approved:
            unexpected = sorted(proposed - approved)
            raise PermissionError(f"Changement hors plan approuvé : {unexpected}")
        self.guard.ensure_file_budget(already_changed | proposed)
        results: list[ToolResult] = []
        for change in changes:
            target = self.guard.resolve(change.path, for_write=True)
            operation = (
                self.filesystem.write_file
                if target.exists()
                else self.filesystem.create_file
            )
            result = operation(change.path, change.content)
            results.append(result)
            if not result.ok:
                break
            already_changed.add(change.path)
        return results

    def _read_context(self, paths: list[str]) -> dict[str, str]:
        context: dict[str, str] = {}
        for path in paths[: self.guard.config.max_files_changed]:
            result = self.filesystem.read_file(path)
            if result.ok:
                context[path] = str(result.data["content"])
        return context

    def _remote_changes(self, prompt_name: str, plan: Plan, **extra: Any) -> list[FileChange]:
        system = (self.root / "prompts" / "system_prompt.md").read_text(encoding="utf-8")
        instruction = (self.root / "prompts" / prompt_name).read_text(encoding="utf-8")
        response = self.model.complete_json(
            system,
            instruction,
            {"plan": plan.to_dict(), **extra},
        )
        raw_changes = response.get("changes")
        if not isinstance(raw_changes, list):
            raise ValueError("Réponse codeur invalide : changes doit être une liste.")
        changes = [FileChange.from_dict(item) for item in raw_changes]
        self.guard.ensure_file_budget({change.path for change in changes})
        return changes
