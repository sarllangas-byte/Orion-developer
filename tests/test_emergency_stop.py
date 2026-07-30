from agent.main import OrionEngine
from agent.state import MissionStatus


def test_stop_file_cancels_before_analysis(orion_config):
    stop_file = orion_config.workspace / "STOP_AGENT"
    stop_file.touch()
    engine = OrionEngine(orion_config)
    exit_code = engine.run("Ajouter un score RGA")
    assert exit_code == 2
    with engine.memory.connect() as connection:
        status = connection.execute(
            "SELECT status FROM objectives ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
    assert status == MissionStatus.CANCELLED.value
    assert engine.git.current_branch() == "main"
