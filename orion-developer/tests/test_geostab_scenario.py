from agent.approval import ApprovalGate
from agent.main import OrionEngine


def test_complete_offline_rga_scenario(orion_config, monkeypatch):
    monkeypatch.setenv("ORION_OFFLINE", "true")
    approval = ApprovalGate(lambda _question: "oui")
    engine = OrionEngine(orion_config, approval)

    exit_code = engine.run(
        "Ajouter une fonction de calcul du score d'exposition RGA.",
        plan_preapproved=True,
    )

    assert exit_code == 0
    assert engine.git.current_branch().startswith("orion/objective-")
    assert (orion_config.workspace / "geostab_demo" / "rga.py").is_file()
    assert (orion_config.workspace / "tests" / "test_rga.py").is_file()
    status = engine.git.get_git_status()
    assert "geostab_demo/rga.py" in status.data["output"]
    assert "tests/test_rga.py" in status.data["output"]
