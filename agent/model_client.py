"""Client distant sans dépendance, limité aux réponses JSON."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from agent.config import ModelConfig
from tools.audit import AuditLogger


class ModelUnavailable(RuntimeError):
    """Le modèle distant est désactivé ou inaccessible."""


class GitHubModelsClient:
    def __init__(self, config: ModelConfig, audit: AuditLogger) -> None:
        self.config = config
        self.audit = audit

    @property
    def available(self) -> bool:
        offline = os.getenv("ORION_OFFLINE", "false").lower() in {"1", "true", "yes"}
        return bool(self._token()) and not offline

    def complete_json(
        self,
        system: str,
        instruction: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        token = self._token()
        if not self.available or not token:
            raise ModelUnavailable(
                "Aucun jeton GitHub Models disponible. Utilisez le scénario RGA hors-ligne "
                "ou définissez GITHUB_MODELS_TOKEN."
            )
        body = {
            "model": self.config.name,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": (
                        instruction
                        + "\n\nENTRÉE JSON:\n"
                        + json.dumps(payload, ensure_ascii=False)
                    ),
                },
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            self.config.endpoint,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2026-03-10",
                "User-Agent": "orion-developer-v1",
            },
        )
        self.audit.log("model_request", model=self.config.name, payload_keys=list(payload))
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw_response = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            self.audit.log("model_error", status=exc.code, detail=detail)
            raise ModelUnavailable(f"GitHub Models HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            self.audit.log("model_error", error=str(exc))
            raise ModelUnavailable(f"GitHub Models inaccessible : {exc}") from exc

        try:
            content = raw_response["choices"][0]["message"]["content"]
            parsed = self._parse_json(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Réponse du modèle non conforme au contrat JSON.") from exc
        self.audit.log("model_response", model=self.config.name, keys=list(parsed))
        return parsed

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        cleaned = content.strip()
        fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
        if fence:
            cleaned = fence.group(1)
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("La réponse JSON doit être un objet.")
        return parsed

    @staticmethod
    def _token() -> str:
        return os.getenv("GITHUB_MODELS_TOKEN", "")
