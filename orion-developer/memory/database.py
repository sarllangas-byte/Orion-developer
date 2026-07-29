"""API minimale et paramétrée pour la mémoire SQLite."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class MemoryDatabase:
    def __init__(self, path: Path, schema_path: Path | None = None) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        default_schema = Path(__file__).with_name("schema.sql")
        self.schema_path = (schema_path or default_schema).resolve()
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        schema = self.schema_path.read_text(encoding="utf-8")
        with self.connect() as connection:
            connection.executescript(schema)

    def create_objective(self, description: str) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO objectives(description) VALUES (?)", (description,)
            )
            return int(cursor.lastrowid)

    def set_objective_status(self, objective_id: int, status: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE objectives
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, objective_id),
            )

    def create_task(self, objective_id: int, title: str) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO tasks(objective_id, title) VALUES (?, ?)",
                (objective_id, title),
            )
            return int(cursor.lastrowid)

    def save_plan(self, objective_id: int, plan: dict[str, Any]) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO plans(objective_id, plan_json) VALUES (?, ?)",
                (objective_id, json.dumps(plan, ensure_ascii=False)),
            )
            return int(cursor.lastrowid)

    def record_action(
        self,
        *,
        objective_id: int,
        task_id: int | None,
        action_type: str,
        tool_name: str,
        input_summary: str,
        output_summary: str,
        status: str,
        files_changed: list[str] | None = None,
        approval_required: bool = False,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO actions(
                    objective_id, task_id, action_type, tool_name, input_summary,
                    output_summary, status, files_changed_json, approval_required
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    objective_id,
                    task_id,
                    action_type,
                    tool_name,
                    input_summary,
                    output_summary,
                    status,
                    json.dumps(files_changed or [], ensure_ascii=False),
                    int(approval_required),
                ),
            )
            return int(cursor.lastrowid)

    def record_tool_call(
        self,
        action_id: int | None,
        tool_name: str,
        request: dict[str, Any],
        response: dict[str, Any],
        status: str,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO tool_calls(action_id, tool_name, request_json, response_json, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    action_id,
                    tool_name,
                    json.dumps(request, ensure_ascii=False),
                    json.dumps(response, ensure_ascii=False),
                    status,
                ),
            )
            return int(cursor.lastrowid)

    def record_result(self, objective_id: int, kind: str, content: str, status: str) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO results(objective_id, kind, content, status) VALUES (?, ?, ?, ?)",
                (objective_id, kind, content, status),
            )
            return int(cursor.lastrowid)

    def record_error(
        self,
        objective_id: int | None,
        task_id: int | None,
        error_type: str,
        message: str,
        recoverable: bool,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO errors(objective_id, task_id, error_type, message, recoverable)
                VALUES (?, ?, ?, ?, ?)
                """,
                (objective_id, task_id, error_type, message, int(recoverable)),
            )
            return int(cursor.lastrowid)

    def record_approval(
        self, objective_id: int, stage: str, decision: str, comment: str = ""
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO approvals(objective_id, stage, decision, comment)
                VALUES (?, ?, ?, ?)
                """,
                (objective_id, stage, decision, comment),
            )
            return int(cursor.lastrowid)

    def save_lesson(self, objective_id: int | None, lesson: str) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO lessons(objective_id, lesson) VALUES (?, ?)",
                (objective_id, lesson),
            )
            return int(cursor.lastrowid)

    def record_file_change(
        self,
        objective_id: int,
        path: str,
        operation: str,
        before_hash: str | None,
        after_hash: str | None,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO file_changes(objective_id, path, operation, before_hash, after_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                (objective_id, path, operation, before_hash, after_hash),
            )
            return int(cursor.lastrowid)

    def load_memory(self, limit: int = 20) -> dict[str, list[dict[str, Any]]]:
        bounded = max(1, min(limit, 100))
        with self.connect() as connection:
            actions = connection.execute(
                "SELECT * FROM actions ORDER BY id DESC LIMIT ?", (bounded,)
            ).fetchall()
            lessons = connection.execute(
                "SELECT * FROM lessons ORDER BY id DESC LIMIT ?", (bounded,)
            ).fetchall()
        return {
            "actions": [dict(row) for row in actions],
            "lessons": [dict(row) for row in lessons],
        }
