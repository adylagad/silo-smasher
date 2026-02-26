from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests


class SensoAPIError(RuntimeError):
    """Raised when Senso responds with an API error."""


@dataclass
class SensoConfig:
    api_key: str
    base_url: str = "https://sdk.senso.ai/api/v1"
    poll_seconds: int = 2
    timeout_seconds: int = 120

    @classmethod
    def from_env(cls) -> "SensoConfig":
        api_key = os.getenv("SENSO_API_KEY")
        if not api_key:
            raise RuntimeError("SENSO_API_KEY is required when publishing to Senso.")
        return cls(
            api_key=api_key,
            base_url=os.getenv("SENSO_BASE_URL", "https://sdk.senso.ai/api/v1").rstrip("/"),
            poll_seconds=int(os.getenv("SENSO_POLL_SECONDS", "2")),
            timeout_seconds=int(os.getenv("SENSO_TIMEOUT_SECONDS", "120")),
        )


class SensoClient:
    def __init__(self, config: SensoConfig):
        self._config = config
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Content-Type": "application/json",
                "X-API-Key": config.api_key,
            }
        )

    def _url(self, path: str) -> str:
        return f"{self._config.base_url}{path}"

    def _request(
        self,
        method: str,
        path: str,
        expected_statuses: tuple[int, ...],
        json_payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        response = self._session.request(
            method=method,
            url=self._url(path),
            json=json_payload,
            timeout=self._config.timeout_seconds,
        )
        if response.status_code not in expected_statuses:
            raise SensoAPIError(
                f"Senso {method} {path} failed ({response.status_code}): {response.text}"
            )
        if response.content:
            return response.json()
        return {}

    def create_raw_content(self, title: str, summary: str, text: str) -> dict[str, Any]:
        payload = {
            "title": title,
            "summary": summary,
            "text": text,
        }
        return self._request("POST", "/content/raw", (202,), json_payload=payload)

    def get_content(self, content_id: str) -> dict[str, Any]:
        return self._request("GET", f"/content/{content_id}", (200,))

    def wait_for_completed(self, content_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self._config.timeout_seconds
        while True:
            detail = self.get_content(content_id)
            status = str(detail.get("processing_status", "")).lower()
            if status == "completed":
                return detail
            if status == "failed":
                raise SensoAPIError(f"Content {content_id} failed to process.")
            if time.monotonic() > deadline:
                raise TimeoutError(f"Timed out waiting for content {content_id} to complete.")
            time.sleep(self._config.poll_seconds)

