from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


@dataclass
class NavigatorSettings:
    api_key: str | None
    base_url: str
    poll_seconds: float
    task_timeout_seconds: float
    http_timeout_seconds: float
    max_steps: int

    @classmethod
    def from_env(cls) -> "NavigatorSettings":
        return cls(
            api_key=os.getenv("YUTORI_API_KEY"),
            base_url=os.getenv("YUTORI_BASE_URL", "https://api.yutori.com").rstrip("/"),
            poll_seconds=float(os.getenv("YUTORI_POLL_SECONDS", "3")),
            task_timeout_seconds=float(os.getenv("YUTORI_TASK_TIMEOUT_SECONDS", "180")),
            http_timeout_seconds=float(os.getenv("YUTORI_HTTP_TIMEOUT_SECONDS", "30")),
            max_steps=int(os.getenv("YUTORI_MAX_STEPS", "75")),
        )


class NavigatorClient:
    def __init__(self, settings: NavigatorSettings):
        self._settings = settings

    @classmethod
    def from_env(cls) -> "NavigatorClient":
        return cls(settings=NavigatorSettings.from_env())

    def fetch_latest_portal_report(
        self,
        *,
        portal_url: str,
        report_hint: str | None = None,
        task_prompt: str | None = None,
        require_auth: bool = True,
        max_steps: int | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        if not self._settings.api_key:
            return self._local_portal_fallback(
                portal_url=portal_url,
                report_hint=report_hint,
                reason="YUTORI_API_KEY is not configured.",
            )

        instruction = self._build_instruction(report_hint=report_hint, task_prompt=task_prompt)
        chosen_steps = self._clamp_steps(max_steps if max_steps is not None else self._settings.max_steps)
        timeout_limit = max(30.0, timeout_seconds if timeout_seconds is not None else self._settings.task_timeout_seconds)
        created_payload = self._create_task(
            instruction=instruction,
            portal_url=portal_url,
            require_auth=require_auth,
            max_steps=chosen_steps,
        )
        if "error" in created_payload:
            return created_payload

        task_id = self._extract_task_id(created_payload)
        if not task_id:
            return {
                "error": "yutori_task_create_missing_id",
                "created_payload": created_payload,
            }

        deadline = time.monotonic() + timeout_limit
        last_payload = created_payload
        while time.monotonic() < deadline:
            current_payload = self._retrieve_task(task_id)
            if "error" in current_payload:
                return current_payload
            last_payload = current_payload
            status = str(current_payload.get("status", "")).lower()
            if status in {"completed", "succeeded"}:
                return {
                    "task_id": task_id,
                    "status": status,
                    "portal_url": portal_url,
                    "result": current_payload,
                }
            if status in {"failed", "cancelled", "canceled"}:
                return {
                    "task_id": task_id,
                    "status": status,
                    "portal_url": portal_url,
                    "result": current_payload,
                }
            time.sleep(self._settings.poll_seconds)

        return {
            "error": "yutori_task_timeout",
            "task_id": task_id,
            "portal_url": portal_url,
            "timeout_seconds": timeout_limit,
            "last_payload": last_payload,
        }

    def _local_portal_fallback(
        self,
        *,
        portal_url: str,
        report_hint: str | None,
        reason: str,
    ) -> dict[str, Any]:
        context_dir = Path("data/system_of_record/agent_context")
        context_files = sorted(context_dir.glob("context_*.json"))
        latest_context = context_files[-1] if context_files else None

        if latest_context is None:
            return {
                "source": "local_fallback",
                "status": "no_local_report_available",
                "portal_url": portal_url,
                "report_hint": report_hint,
                "fallback_reason": reason,
                "message": (
                    "Web navigation credentials are unavailable and no local system-of-record "
                    "context file was found."
                ),
            }

        try:
            context_payload = json.loads(latest_context.read_text(encoding="utf-8"))
        except Exception as exc:
            return {
                "source": "local_fallback",
                "status": "local_report_read_failed",
                "portal_url": portal_url,
                "report_hint": report_hint,
                "fallback_reason": f"{reason} Failed to read local context: {exc}",
                "local_context_path": str(latest_context),
            }

        facts = context_payload.get("facts", {}) if isinstance(context_payload, dict) else {}
        metrics = facts.get("metrics", {}) if isinstance(facts, dict) else {}
        top_products = facts.get("top_products", []) if isinstance(facts, dict) else []
        generated_at = context_payload.get("generated_at") if isinstance(context_payload, dict) else None

        return {
            "source": "local_fallback",
            "status": "local_report_summary_returned",
            "portal_url": portal_url,
            "report_hint": report_hint,
            "fallback_reason": reason,
            "local_context_path": str(latest_context),
            "local_context_generated_at": generated_at,
            "summary": {
                "metrics": metrics,
                "top_products": top_products[:5] if isinstance(top_products, list) else [],
            },
            "message": (
                "Used local system-of-record context as fallback. Set YUTORI_API_KEY to enable "
                "internal portal browsing and latest PDF retrieval."
            ),
        }

    def _create_task(
        self,
        *,
        instruction: str,
        portal_url: str,
        require_auth: bool,
        max_steps: int,
    ) -> dict[str, Any]:
        url = f"{self._settings.base_url}/v1/browsing/tasks"
        headers = {
            "x-api-key": self._settings.api_key or "",
            "content-type": "application/json",
        }
        payload: dict[str, Any] = {
            "task": instruction,
            "start_url": portal_url,
            "require_auth": require_auth,
            "max_steps": max_steps,
        }
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self._settings.http_timeout_seconds,
            )
            if response.status_code == 422:
                payload.pop("max_steps", None)
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self._settings.http_timeout_seconds,
                )
            response.raise_for_status()
            parsed = response.json()
            return parsed if isinstance(parsed, dict) else {"result": parsed}
        except Exception as exc:
            return {
                "error": "yutori_task_create_failed",
                "detail": str(exc),
                "portal_url": portal_url,
            }

    def _retrieve_task(self, task_id: str) -> dict[str, Any]:
        url = f"{self._settings.base_url}/v1/browsing/tasks/{task_id}"
        headers = {
            "x-api-key": self._settings.api_key or "",
        }
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=self._settings.http_timeout_seconds,
            )
            response.raise_for_status()
            parsed = response.json()
            return parsed if isinstance(parsed, dict) else {"result": parsed}
        except Exception as exc:
            return {
                "error": "yutori_task_retrieve_failed",
                "detail": str(exc),
                "task_id": task_id,
            }

    @staticmethod
    def _extract_task_id(payload: dict[str, Any]) -> str | None:
        for key in ("id", "task_id"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        nested = payload.get("task")
        if isinstance(nested, dict):
            value = nested.get("id") or nested.get("task_id")
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _clamp_steps(value: int) -> int:
        return max(10, min(int(value), 150))

    @staticmethod
    def _build_instruction(report_hint: str | None, task_prompt: str | None) -> str:
        if task_prompt and task_prompt.strip():
            return task_prompt.strip()
        hint = report_hint.strip() if report_hint else "latest performance report"
        return (
            "Log into the internal portal if required, find the latest PDF report related to "
            f"'{hint}', and extract grounded evidence. Return report metadata (title, publication "
            "date, URL), the key KPIs, and short quotes/snippets that support conclusions."
        )
