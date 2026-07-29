"""Création de rapports Markdown dans le dossier interne prévu."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from agent.state import ToolResult
from tools.audit import AuditLogger


class ReportTools:
    def __init__(self, reports_directory: Path, audit: AuditLogger) -> None:
        self.reports_directory = reports_directory.resolve()
        self.reports_directory.mkdir(parents=True, exist_ok=True)
        self.audit = audit

    def create_report(self, objective_id: int, content: str) -> ToolResult:
        safe_id = re.sub(r"[^0-9]", "", str(objective_id))
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        target = self.reports_directory / f"objective-{safe_id}-{stamp}.md"
        target.write_text(content, encoding="utf-8")
        result = ToolResult(
            True,
            "create_report",
            "Rapport créé.",
            {"path": str(target)},
        )
        self.audit.log("tool_call", tool="create_report", result=result.to_dict())
        return result
