import sqlite3
from pathlib import Path

from memory.database import MemoryDatabase


def test_sqlite_memory_contains_all_required_tables(tmp_path: Path):
    database = MemoryDatabase(tmp_path / "orion.db")
    required = {
        "objectives",
        "tasks",
        "plans",
        "actions",
        "tool_calls",
        "results",
        "errors",
        "approvals",
        "lessons",
        "file_changes",
    }
    with sqlite3.connect(database.path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert required <= tables


def test_memory_round_trip(tmp_path: Path):
    database = MemoryDatabase(tmp_path / "orion.db")
    objective_id = database.create_objective("Ajouter un test")
    task_id = database.create_task(objective_id, "Écrire le test")
    database.record_action(
        objective_id=objective_id,
        task_id=task_id,
        action_type="test",
        tool_name="run_tests",
        input_summary="pytest",
        output_summary="ok",
        status="success",
        files_changed=["tests/test_demo.py"],
    )
    database.save_lesson(objective_id, "Toujours tester les limites.")

    memory = database.load_memory()

    assert memory["actions"][0]["tool_name"] == "run_tests"
    assert memory["lessons"][0]["lesson"] == "Toujours tester les limites."
