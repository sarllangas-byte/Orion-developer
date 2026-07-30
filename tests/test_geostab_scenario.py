from agent.approval import ApprovalGate
from agent.main import OrionEngine


def test_complete_offline_rga_scenario(orion_config, monkeypatch):
    monkeypatch.setenv("ORION_OFFLINE", "true")
    approval = ApprovalGate(lambda _question: "APPROVE")
    engine = OrionEngine(orion_config, approval)

    exit_code = engine.run(
        "Ajouter calculate_rga_exposure_score pour le RGA.",
        plan_preapproved=True,
    )

    assert exit_code == 0
    assert engine.git.current_branch().startswith("agent/001-")
    scoring = orion_config.workspace / "geostab" / "scoring.py"
    tests = orion_config.workspace / "tests" / "test_scoring.py"
    assert "calculate_rga_exposure_score" in scoring.read_text(encoding="utf-8")
    assert tests.is_file()
    status = engine.git.get_git_status()
    assert "geostab/scoring.py" in status.data["output"]
    assert "tests/test_scoring.py" in status.data["output"]
