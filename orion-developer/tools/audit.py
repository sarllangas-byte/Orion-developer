"""Journal JSONL local, sans secrets ni contenu intégral de fichiers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class AuditLogger:
    REDACTED_KEYS = {"token", "authorization", "password", "secret", "api_key"}

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, **details: Any) -> None:
        record = {
            "created_at": datetime.now(UTC).isoformat(),
            "event": event,
            "details": self._redact(details),
        }
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: (
                    "[MASQUÉ]"
                    if any(marker in key.lower() for marker in self.REDACTED_KEYS)
                    else self._redact(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list | tuple):
            return [self._redact(item) for item in value]
        return value
