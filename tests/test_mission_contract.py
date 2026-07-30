from agent.approval import ApprovalGate
from agent.state import ApprovalDecision, Mission, MissionStatus, Plan


def test_structured_mission_defaults_and_statuses():
    mission = Mission.from_dict({"objective": "Ajouter un score"})
    assert mission.status is MissionStatus.CREATED
    assert mission.max_files_changed == 5
    assert mission.max_iterations == 10


def test_all_approval_decisions_are_supported():
    for raw, expected in {
        "APPROVE": ApprovalDecision.APPROVE,
        "REJECT": ApprovalDecision.REJECT,
        "REQUEST_CHANGES": ApprovalDecision.REQUEST_CHANGES,
        "CANCEL": ApprovalDecision.CANCEL,
    }.items():
        gate = ApprovalGate(lambda _question, answer=raw: answer)
        assert gate.request_decision("PLAN", "Décision ?") is expected


def test_plan_contains_operational_fields():
    plan = Plan.from_dict(
        {
            "objective": "Objectif",
            "understanding": "Compréhension",
            "files_to_read": [],
            "files_to_modify": [],
            "files_to_create": ["module.py"],
            "implementation_steps": ["Créer"],
            "tests_to_create": ["tests/test_module.py"],
            "tests_to_run": ["python -m pytest -q"],
            "risks": [],
            "rollback_strategy": "Restaurer",
            "estimated_complexity": "low",
        }
    )
    assert plan.files_to_create == ["module.py"]
    assert plan.rollback_strategy == "Restaurer"
