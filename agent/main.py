"""CLI et chaîne contrôlée d'ORION Developer V1."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from agent.analyzer import RepositoryAnalyzer
from agent.approval import ApprovalGate
from agent.config import OrionConfig, load_config
from agent.evaluator import Evaluation, Evaluator, QualityEvaluation
from agent.executor import Executor
from agent.model_client import GitHubModelsClient
from agent.planner import Planner
from agent.state import (
    ApprovalDecision,
    FinalDecision,
    Mission,
    MissionStatus,
    Plan,
    RunState,
    ToolResult,
)
from memory.database import MemoryDatabase
from tools.audit import AuditLogger
from tools.filesystem_tools import FileSystemTools
from tools.git_tools import GitTools
from tools.report_tools import ReportTools
from tools.security_tools import SecurityGuard
from tools.test_tools import TestTools

MAX_CORRECTION_ATTEMPTS = 3
MAX_TOTAL_ITERATIONS = 10
MAX_IDENTICAL_ERRORS = 2


class OrionEngine:
    """MISSION → ANALYSE → PLAN → AUTORISATION → BRANCHE → MODIFICATION →
    TESTS → CORRECTION → AUDIT → RAPPORT → ARRÊT.
    """

    def __init__(self, config: OrionConfig, approval: ApprovalGate | None = None) -> None:
        self.config = config
        self.approval = approval or ApprovalGate()
        self.memory = MemoryDatabase(config.database)
        self.audit = AuditLogger(config.logs)
        self.guard = SecurityGuard(config.workspace, config.safety)
        self.git = GitTools(config.workspace, self.guard, self.audit)
        self.filesystem = FileSystemTools(self.guard, self.git.get_current_branch, self.audit)
        self.test_tools = TestTools(
            config.workspace,
            config.test_command,
            config.lint_command,
            self.audit,
            allowed_commands=config.allowed_commands,
        )
        self.model = GitHubModelsClient(config.model, self.audit)
        self.planner = Planner(config.root, self.model)
        self.executor = Executor(config.root, self.model, self.filesystem, self.guard)
        self.evaluator = Evaluator(self.test_tools)
        self.analyzer = RepositoryAnalyzer(self.filesystem, self.guard)
        self.reports = ReportTools(config.reports, self.audit)

    @property
    def stop_files(self) -> tuple[Path, Path]:
        return (self.config.root / "STOP_AGENT", self.config.workspace / "STOP_AGENT")

    def stop_requested(self) -> bool:
        return any(path.is_file() for path in self.stop_files)

    def run(
        self,
        objective: str | None = None,
        *,
        mission: Mission | None = None,
        plan_preapproved: bool = False,
        dry_run: bool = False,
    ) -> int:
        mission = mission or Mission.from_dict({"objective": objective or ""})
        try:
            expected_repository = self.config.workspace.relative_to(self.config.root).as_posix()
        except ValueError:
            # Les tests peuvent injecter un workspace temporaire hors de la racine applicative.
            expected_repository = mission.repository
        if mission.repository.replace("\\", "/").strip("/") != expected_repository:
            raise PermissionError(
                f"Cette instance ORION est confinée à {expected_repository}, "
                f"pas à {mission.repository}."
            )
        if not self.config.workspace.is_dir() or not self.git.is_repository():
            raise RuntimeError(
                "Le bac à sable doit être un dépôt Git. Lancez : python scripts/bootstrap_demo.py"
            )

        objective_id = self.memory.create_objective(mission.objective)
        mission.mission_id = f"{objective_id:03d}"
        state = RunState(objective_id, mission.objective)
        state.task_id = self.memory.create_task(objective_id, "Exécuter la mission approuvée")
        self.memory.save_mission(objective_id, mission.to_dict())
        self._set_status(mission, MissionStatus.CREATED)
        self.audit.log("mission_created", mission=mission.to_dict())
        if self._cancel_if_requested(mission):
            return 2

        print("1. ANALYSE")
        self._set_status(mission, MissionStatus.ANALYZING)
        repository_map = self.analyzer.analyze(mission.objective)
        listing = self.filesystem.list_files()
        self._record_tool(state, "analysis", listing)
        print(json.dumps(repository_map.to_dict(), ensure_ascii=False, indent=2))
        if self._cancel_if_requested(mission):
            return 2

        print("2. PLAN")
        try:
            plan = self.planner.create_plan(
                mission.objective,
                list(listing.data["files"]),
                repository_map,
            )
            self._validate_plan(plan, mission.max_files_changed)
        except Exception as exc:
            return self._fail(state, mission, f"Planification impossible : {exc}")
        self.memory.save_plan(objective_id, plan.to_dict())
        self._set_status(mission, MissionStatus.PLANNED)
        print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
        if dry_run:
            mission.results.append("Plan produit sans écriture.")
            self._set_status(mission, MissionStatus.COMPLETED)
            print("DRY-RUN terminé : aucune branche et aucun fichier modifié.")
            return 0

        print("3. AUTORISATION")
        self._set_status(mission, MissionStatus.WAITING_APPROVAL)
        decision = (
            ApprovalDecision.APPROVE
            if plan_preapproved
            else self.approval.request_decision(
                "PLAN", "Autorisez-vous exactement ce plan et ces fichiers ?"
            )
        )
        self.memory.record_approval(objective_id, "plan", decision.value)
        if decision is ApprovalDecision.CANCEL:
            self._set_status(mission, MissionStatus.CANCELLED)
            print("Mission annulée. Aucune modification effectuée.")
            return 2
        if decision is not ApprovalDecision.APPROVE:
            self._set_status(mission, MissionStatus.FAILED)
            print(
                "Plan rejeté ou changements demandés. Relancez une nouvelle mission après révision."
            )
            return 2
        if self._cancel_if_requested(mission):
            return 2

        print("4. BRANCHE")
        branch_result = self.git.create_work_branch(objective_id, mission.objective)
        self._record_tool(state, "git", branch_result)
        if not branch_result.ok:
            return self._fail(state, mission, branch_result.error or "Branche impossible.")
        branch = str(branch_result.data["branch"])
        if self._cancel_if_requested(mission):
            return 2
        baseline = self.evaluator.evaluate()
        if not baseline.passed:
            return self._fail(
                state, mission, "Le projet de référence est déjà dégradé ; aucune écriture."
            )

        print("5. MODIFICATION")
        self._set_status(mission, MissionStatus.EXECUTING)
        try:
            changes = self.executor.propose_changes(plan)
            results = self.executor.apply_changes(
                changes,
                plan.files_to_modify + plan.files_to_create,
                state.files_changed,
                max_files=mission.max_files_changed,
            )
        except Exception as exc:
            return self._fail(state, mission, f"Exécution refusée : {exc}")
        for result in results:
            self._record_file_result(state, result)
        if not results or not all(result.ok for result in results):
            return self._fail(
                state,
                mission,
                results[-1].error if results else "Aucun changement proposé.",
            )
        if self._cancel_if_requested(mission):
            return 2

        print("6. TESTS / CORRECTION")
        evaluation = self._evaluate_with_bounded_corrections(state, mission, plan)
        if mission.status is MissionStatus.CANCELLED:
            print("Mission annulée au prochain point sûr.")
            return 2
        for result in evaluation.results:
            print(json.dumps(result.data, ensure_ascii=False, indent=2))

        print("7. AUDIT")
        diff_result = self.git.get_git_diff()
        self._record_tool(state, "audit", diff_result)
        if not diff_result.ok:
            return self._fail(state, mission, diff_result.error or "Diff indisponible.")
        diff = str(diff_result.data["diff"])
        quality = self.evaluator.quality_review(plan, state.files_changed, evaluation, diff)
        final_decision = (
            FinalDecision.READY_FOR_REVIEW
            if quality.recommendation == "READY_FOR_HUMAN_REVIEW"
            else FinalDecision.HUMAN_INTERVENTION_REQUIRED
        )
        self._set_status(
            mission,
            MissionStatus.COMPLETED if evaluation.passed else MissionStatus.FAILED,
        )

        print("8. RAPPORT")
        report = self._build_report(
            mission,
            plan,
            repository_map.to_dict(),
            branch,
            state,
            evaluation,
            quality,
            diff,
            final_decision,
        )
        report_result = self.reports.create_report(objective_id, report)
        self._record_tool(state, "report", report_result)
        mission.results.append(str(report_result.data.get("path", "")))
        self.memory.record_result(objective_id, "final_report", report, final_decision.value)
        print(f"9. ARRÊT — {final_decision.value}")
        print("Aucun commit, push, merge ou déploiement n'a été effectué.")
        return 0 if evaluation.passed and quality.security_passed else 1

    def _evaluate_with_bounded_corrections(
        self, state: RunState, mission: Mission, plan: Plan
    ) -> Evaluation:
        while True:
            if self.stop_requested():
                self._set_status(mission, MissionStatus.CANCELLED)
                return Evaluation(False, [ToolResult(False, "stop", "Arrêt demandé.")])
            state.next_iteration(
                min(
                    mission.max_iterations,
                    self.config.safety.max_iterations,
                    MAX_TOTAL_ITERATIONS,
                )
            )
            self._set_status(mission, MissionStatus.TESTING)
            evaluation = self.evaluator.evaluate()
            for result in evaluation.results:
                self._record_tool(state, "test", result)
            if evaluation.passed:
                return evaluation
            fingerprint = hashlib.sha256(
                evaluation.combined_output[-5000:].encode("utf-8")
            ).hexdigest()
            try:
                state.record_error(
                    fingerprint,
                    min(self.config.safety.max_identical_errors, MAX_IDENTICAL_ERRORS),
                )
                state.next_retry(
                    min(
                        self.config.safety.max_retries_per_task,
                        MAX_CORRECTION_ATTEMPTS,
                    )
                )
                self._set_status(mission, MissionStatus.CORRECTING)
                corrections = self.executor.propose_correction(plan, evaluation.combined_output)
                if not corrections:
                    return evaluation
                results = self.executor.apply_changes(
                    corrections,
                    plan.files_to_modify + plan.files_to_create,
                    state.files_changed,
                    max_files=mission.max_files_changed,
                )
                for result in results:
                    self._record_file_result(state, result)
                if not all(result.ok for result in results):
                    return evaluation
            except Exception as exc:
                mission.errors.append(str(exc))
                self.memory.record_error(
                    state.objective_id, state.task_id, type(exc).__name__, str(exc), False
                )
                return evaluation

    def _validate_plan(self, plan: Plan, maximum: int) -> None:
        write_paths = plan.files_to_modify + plan.files_to_create
        self.guard.ensure_file_budget(set(write_paths), maximum)
        for path in plan.files_to_read:
            self.guard.resolve(path)
        for path in write_paths:
            self.guard.resolve(path, for_write=True)

    def _record_file_result(self, state: RunState, result: ToolResult) -> None:
        self._record_tool(state, "file_change", result)
        if result.ok:
            self.memory.record_file_change(
                state.objective_id,
                str(result.data["path"]),
                str(result.data.get("operation", result.tool)),
                result.data.get("before_hash"),
                result.data.get("after_hash"),
            )

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
        )
        self.memory.record_tool_call(
            action_id,
            result.tool,
            {"content": "non journalisé"},
            result.to_dict(),
            "success" if result.ok else "error",
        )

    def _set_status(self, mission: Mission, status: MissionStatus) -> None:
        mission.status = status
        if mission.mission_id:
            self.memory.set_objective_status(int(mission.mission_id), status.value)
            self.memory.save_mission(int(mission.mission_id), mission.to_dict())
        self.audit.log("mission_status", mission_id=mission.mission_id, status=status.value)

    def _cancel_if_requested(self, mission: Mission) -> bool:
        if not self.stop_requested():
            return False
        self._set_status(mission, MissionStatus.CANCELLED)
        print("ARRÊT D'URGENCE : STOP_AGENT détecté. Aucune autre action.")
        return True

    def _fail(self, state: RunState, mission: Mission, message: str) -> int:
        mission.errors.append(message)
        self.memory.record_error(state.objective_id, state.task_id, "OrionRunError", message, False)
        self._set_status(mission, MissionStatus.FAILED)
        print(f"ARRÊT SÉCURISÉ : {message}", file=sys.stderr)
        return 1

    @staticmethod
    def _build_report(
        mission: Mission,
        plan: Plan,
        repository_map: dict[str, object],
        branch: str,
        state: RunState,
        evaluation: Evaluation,
        quality: QualityEvaluation,
        diff: str,
        final_decision: FinalDecision,
    ) -> str:
        test_results = [result.data for result in evaluation.results]
        plan_json = json.dumps(plan.to_dict(), ensure_ascii=False, indent=2)
        map_json = json.dumps(repository_map, ensure_ascii=False, indent=2)
        tests_json = json.dumps(test_results, ensure_ascii=False, indent=2)
        quality_json = json.dumps(quality.to_dict(), ensure_ascii=False, indent=2)
        return (
            f"# Rapport ORION — mission {mission.mission_id}\n\n"
            f"## Mission\n\nStatut : `{mission.status.value}`\n\n"
            f"## Objectif\n\n{mission.objective}\n\n"
            f"## Plan exécuté\n\n```json\n{plan_json}\n```\n\n"
            f"## Branche\n\n`{branch}`\n\n"
            f"## Fichiers lus\n\n{', '.join(plan.files_to_read) or '(aucun)'}\n\n"
            f"## Fichiers modifiés ou créés\n\n{', '.join(sorted(state.files_changed))}\n\n"
            f"## Cartographie\n\n```json\n{map_json}\n```\n\n"
            f"## Tests et résultats\n\n```json\n{tests_json}\n```\n\n"
            f"## Erreurs et corrections\n\n{', '.join(mission.errors) or '(aucune)'}\n\n"
            f"## Risques\n\n" + "\n".join(f"- {risk}" for risk in plan.risks) + "\n\n"
            f"## Audit qualité\n\n```json\n{quality_json}\n```\n\n"
            f"## Diff\n\n```diff\n{diff}\n```\n\n"
            f"## Recommandation\n\n`{final_decision.value}`\n\n"
            "ORION s'arrête ici. Aucun merge ni déploiement automatique.\n"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ORION Developer V1")
    parser.add_argument("command", nargs="?", choices=("run", "stop", "status"), default="run")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--objective")
    parser.add_argument("--mission", help="Fichier JSON de mission structurée")
    parser.add_argument("--approve-plan", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        config = load_config(Path(arguments.config))
        stop_file = config.root / "STOP_AGENT"
        if arguments.command == "stop":
            stop_file.touch(exist_ok=True)
            print(f"Arrêt demandé : {stop_file}")
            return 0
        if arguments.command == "status":
            latest = MemoryDatabase(config.database).latest_mission()
            print(
                json.dumps(
                    {
                        "stop_requested": stop_file.is_file(),
                        "workspace": str(config.workspace),
                        "repository_ready": (config.workspace / ".git").is_dir(),
                        "latest_mission": latest,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        mission = None
        if arguments.mission:
            raw = json.loads(Path(arguments.mission).read_text(encoding="utf-8"))
            mission = Mission.from_dict(raw)
        objective = arguments.objective or (None if mission else input("Objectif : ").strip())
        return OrionEngine(config).run(
            objective,
            mission=mission,
            plan_preapproved=arguments.approve_plan,
            dry_run=arguments.dry_run,
        )
    except KeyboardInterrupt:
        print("\nARRÊT IMMÉDIAT demandé.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ARRÊT SÉCURISÉ : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
