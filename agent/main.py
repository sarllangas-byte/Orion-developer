"""Interface CLI et orchestration contrôlée d'ORION Developer V1."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent.approval import ApprovalGate
from agent.config import OrionConfig, load_config
from agent.evaluator import Evaluation, Evaluator
from agent.executor import Executor
from agent.model_client import GitHubModelsClient
from agent.planner import Planner
from agent.state import RunState, ToolResult
from memory.database import MemoryDatabase
from tools.audit import AuditLogger
from tools.filesystem_tools import FileSystemTools
from tools.git_tools import GitTools
from tools.report_tools import ReportTools
from tools.security_tools import SecurityGuard
from tools.test_tools import TestTools


class OrionEngine:
    """Boucle bornée. Le moteur ne sait ni fusionner, ni pousser, ni déployer."""

    def __init__(self, config: OrionConfig, approval: ApprovalGate | None = None) -> None:
        self.config = config
        self.approval = approval or ApprovalGate()
        self.memory = MemoryDatabase(config.database)
        self.audit = AuditLogger(config.logs)
        self.guard = SecurityGuard(config.workspace, config.safety)
        self.git = GitTools(config.workspace, self.guard, self.audit)
        self.filesystem = FileSystemTools(
            self.guard,
            self.git.current_branch,
            self.audit,
        )
        self.test_tools = TestTools(
            config.workspace,
            config.test_command,
            config.lint_command,
            self.audit,
        )
        self.model = GitHubModelsClient(config.model, self.audit)
        self.planner = Planner(config.root, self.model)
        self.executor = Executor(config.root, self.model, self.filesystem, self.guard)
        self.evaluator = Evaluator(self.test_tools)
        self.reports = ReportTools(config.reports, self.audit)

    def run(self, objective: str, *, plan_preapproved: bool = False, dry_run: bool = False) -> int:
        objective = objective.strip()
        if not objective:
            raise ValueError("L'objectif ne peut pas être vide.")
        if not self.config.workspace.is_dir() or not self.git.is_repository():
            raise RuntimeError(
                "Le workspace doit être un dépôt Git. Lancez d'abord : "
                "python scripts/bootstrap_demo.py"
            )

        objective_id = self.memory.create_objective(objective)
        state = RunState(objective_id=objective_id, objective=objective)
        state.task_id = self.memory.create_task(objective_id, "Implémenter l'objectif approuvé")
        self.audit.log("objective_received", objective_id=objective_id, objective=objective)

        print("1. Analyse du dépôt")
        listing = self.filesystem.list_files()
        self._record_tool(state, "analysis", listing)
        if not listing.ok:
            return self._fail(state, listing.error or "Analyse impossible.")

        print("2. Plan proposé")
        try:
            plan = self.planner.create_plan(objective, list(listing.data["files"]))
            self._validate_plan_paths(plan.files_to_read, plan.files_to_modify)
        except Exception as exc:
            return self._fail(state, f"Planification impossible : {exc}")
        self.memory.save_plan(objective_id, plan.to_dict())
        print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
        print("3. Fichiers concernés :", ", ".join(plan.files_to_modify))
        print("4. Risques identifiés :", " | ".join(plan.risks))

        if dry_run:
            self.memory.set_objective_status(objective_id, "dry_run_complete")
            print("Mode dry-run : aucune branche et aucun fichier modifié.")
            return 0

        approved = plan_preapproved or self.approval.request_approval(
            "PÉRIMÈTRE", "Approuvez-vous ce plan et ces fichiers ?"
        )
        self.memory.record_approval(
            objective_id,
            "plan",
            "approved" if approved else "rejected",
            "Approbation CLI explicite" if plan_preapproved else "",
        )
        if not approved:
            self.memory.set_objective_status(objective_id, "plan_rejected")
            print("Plan refusé. Aucune modification effectuée.")
            return 2

        branch = self.guard.safe_branch_name(objective_id)
        branch_result = self.git.create_git_branch(branch)
        self._record_tool(state, "git", branch_result)
        if not branch_result.ok:
            return self._fail(state, branch_result.error or "Branche impossible.")
        print("5. Branche créée :", branch)

        try:
            changes = self.executor.propose_changes(plan)
            results = self.executor.apply_changes(
                changes,
                plan.files_to_modify,
                state.files_changed,
            )
        except Exception as exc:
            return self._fail(state, f"Exécution refusée : {exc}")
        for result in results:
            self._record_tool(state, "file_change", result)
            if result.ok:
                self.memory.record_file_change(
                    objective_id,
                    str(result.data["path"]),
                    result.tool,
                    result.data.get("before_hash"),
                    result.data.get("after_hash"),
                )
        if not results or not all(result.ok for result in results):
            detail = results[-1].error if results else "Aucun changement proposé."
            return self._fail(state, detail or "Écriture incomplète.")
        print("6. Modifications réalisées :", ", ".join(sorted(state.files_changed)))

        evaluation = self._evaluate_with_bounded_corrections(state, plan)
        print("7. Résultats des tests")
        print(evaluation.combined_output)

        diff_result = self.git.show_diff()
        self._record_tool(state, "audit", diff_result)
        if not diff_result.ok:
            return self._fail(state, diff_result.error or "Diff indisponible.")
        diff = str(diff_result.data["diff"])
        print("8. Diff final")
        print(diff or "(diff vide)")

        report = self._build_report(state, plan.to_dict(), branch, evaluation, diff)
        report_result = self.reports.create_report(objective_id, report)
        self._record_tool(state, "report", report_result)
        self.memory.record_result(
            objective_id,
            "final_audit",
            report_result.data.get("path", ""),
            "tests_passed" if evaluation.passed else "tests_failed",
        )

        print("9. Demande de validation")
        if not evaluation.passed:
            self.memory.set_objective_status(objective_id, "tests_failed")
            print("Validation finale bloquée : les tests ou le linter échouent.")
            return 1
        final_approval = self.approval.request_approval(
            "RÉSULTAT",
            "Acceptez-vous le résultat pour préparer vous-même une pull request ?",
        )
        self.memory.record_approval(
            objective_id,
            "result",
            "approved" if final_approval else "rejected",
        )
        self.memory.set_objective_status(
            objective_id, "human_approved" if final_approval else "human_rejected"
        )
        if final_approval:
            print(
                "Résultat accepté. ORION s'arrête ici : aucun commit, push, PR, merge "
                "ou déploiement automatique."
            )
            return 0
        print("Résultat refusé. Les changements restent visibles sur la branche isolée.")
        return 2

    def _evaluate_with_bounded_corrections(self, state: RunState, plan: object) -> Evaluation:
        while True:
            state.next_iteration(self.config.safety.max_iterations)
            evaluation = self.evaluator.evaluate()
            self._record_tool(state, "test", evaluation.tests)
            if evaluation.linter:
                self._record_tool(state, "lint", evaluation.linter)
            if evaluation.passed:
                return evaluation
            try:
                state.next_retry(self.config.safety.max_retries_per_task)
                corrections = self.executor.propose_correction(plan, evaluation.combined_output)  # type: ignore[arg-type]
                if not corrections:
                    return evaluation
                results = self.executor.apply_changes(
                    corrections,
                    plan.files_to_modify,  # type: ignore[attr-defined]
                    state.files_changed,
                )
                for result in results:
                    self._record_tool(state, "correction", result)
                if not all(result.ok for result in results):
                    return evaluation
            except Exception as exc:
                self.memory.record_error(
                    state.objective_id,
                    state.task_id,
                    type(exc).__name__,
                    str(exc),
                    False,
                )
                return evaluation

    def _validate_plan_paths(self, read_paths: list[str], write_paths: list[str]) -> None:
        self.guard.ensure_file_budget(set(write_paths))
        for path in read_paths:
            self.guard.resolve(path)
        for path in write_paths:
            self.guard.resolve(path, for_write=True)

    def _record_tool(self, state: RunState, action_type: str, result: ToolResult) -> None:
        action_id = self.memory.record_action(
            objective_id=state.objective_id,
            task_id=state.task_id,
            action_type=action_type,
            tool_name=result.tool,
            input_summary="Entrée validée par le moteur",
            output_summary=result.summary,
            status="success" if result.ok else "error",
            files_changed=sorted(state.files_changed),
            approval_required=False,
        )
        self.memory.record_tool_call(
            action_id,
            result.tool,
            {"content": "non journalisé"},
            result.to_dict(),
            "success" if result.ok else "error",
        )

    def _fail(self, state: RunState, message: str) -> int:
        self.memory.record_error(
            state.objective_id,
            state.task_id,
            "OrionRunError",
            message,
            False,
        )
        self.memory.set_objective_status(state.objective_id, "failed")
        print(f"ARRÊT SÉCURISÉ : {message}", file=sys.stderr)
        return 1

    @staticmethod
    def _build_report(
        state: RunState,
        plan: dict[str, object],
        branch: str,
        evaluation: Evaluation,
        diff: str,
    ) -> str:
        return (
            f"# Rapport ORION — objectif {state.objective_id}\n\n"
            f"## Objectif\n\n{state.objective}\n\n"
            f"## Branche\n\n`{branch}`\n\n"
            f"## Plan\n\n```json\n{json.dumps(plan, ensure_ascii=False, indent=2)}\n```\n\n"
            f"## Fichiers modifiés\n\n{', '.join(sorted(state.files_changed))}\n\n"
            f"## Tests et lint\n\nSuccès : `{evaluation.passed}`\n\n"
            f"```text\n{evaluation.combined_output}\n```\n\n"
            f"## Diff\n\n```diff\n{diff}\n```\n\n"
            "Aucune fusion ni aucun déploiement n'a été effectué.\n"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ORION Developer V1")
    parser.add_argument("--config", default="config.yaml", help="Chemin du fichier config.yaml")
    parser.add_argument("--objective", help="Objectif de la mission")
    parser.add_argument(
        "--approve-plan",
        action="store_true",
        help="Approbation explicite du plan via la ligne de commande",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyse et plan uniquement, sans écriture",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    objective = arguments.objective or input("Objectif : ").strip()
    try:
        config = load_config(Path(arguments.config))
        return OrionEngine(config).run(
            objective,
            plan_preapproved=arguments.approve_plan,
            dry_run=arguments.dry_run,
        )
    except KeyboardInterrupt:
        print("\nARRÊT IMMÉDIAT demandé. Aucun merge ni déploiement.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ARRÊT SÉCURISÉ : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
