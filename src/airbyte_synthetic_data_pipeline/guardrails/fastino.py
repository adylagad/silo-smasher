from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

import requests


PII_SCHEMA = [
    "person_name",
    "email_address",
    "phone_number",
    "street_address",
    "ssn",
    "credit_card_number",
    "bank_account_number",
]

ACTION_CATEGORIES = [
    "safe_operation",
    "dangerous_financial_action",
    "credential_exposure",
    "data_exfiltration",
    "destructive_data_change",
]

BLOCKED_ACTION_CATEGORIES = {
    "dangerous_financial_action",
    "credential_exposure",
    "data_exfiltration",
    "destructive_data_change",
}

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CARD_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
BANK_PATTERN = re.compile(r"\b(?:account|routing)\s*(?:number|no\.?)?\s*[:#-]?\s*\d{4,17}\b", re.I)
OPENAI_KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")
AWS_KEY_PATTERN = re.compile(r"\bAKIA[0-9A-Z]{16}\b")

DANGEROUS_ACTION_PATTERN = re.compile(
    r"\b("
    r"wire\s+transfer|transfer\s+funds|send\s+payment|issue\s+refund|"
    r"change\s+bank\s+account|routing\s+number|crypto\s+transfer|"
    r"exfiltrate|delete\s+all|drop\s+table|truncate\s+table"
    r")\b",
    re.I,
)


@dataclass
class FastinoSettings:
    enabled: bool
    api_key: str | None
    base_url: str
    timeout_seconds: float
    pii_threshold: float
    action_threshold: float
    fail_mode: str

    @classmethod
    def from_env(cls) -> "FastinoSettings":
        enabled_value = os.getenv("FASTINO_GUARDRAILS_ENABLED", "true").strip().lower()
        fail_mode = os.getenv("FASTINO_FAIL_MODE", "open").strip().lower()
        if fail_mode not in {"open", "closed"}:
            fail_mode = "open"
        return cls(
            enabled=enabled_value in {"1", "true", "yes", "on"},
            api_key=os.getenv("FASTINO_API_KEY"),
            base_url=os.getenv("FASTINO_BASE_URL", "https://api.fastino.ai").rstrip("/"),
            timeout_seconds=float(os.getenv("FASTINO_TIMEOUT_SECONDS", "10")),
            pii_threshold=float(os.getenv("FASTINO_PII_THRESHOLD", "0.35")),
            action_threshold=float(os.getenv("FASTINO_ACTION_THRESHOLD", "0.5")),
            fail_mode=fail_mode,
        )


@dataclass
class RedactionResult:
    sanitized_text: str
    redactions: list[dict[str, Any]]
    engine: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "error": self.error,
            "redactions": self.redactions,
            "redaction_count": len(self.redactions),
            "input_changed": bool(self.redactions),
        }


@dataclass
class ActionCheckResult:
    allowed: bool
    category: str
    score: float | None
    reason: str
    engine: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "category": self.category,
            "score": self.score,
            "reason": self.reason,
            "engine": self.engine,
            "error": self.error,
        }


class FastinoSafetyEngine:
    def __init__(self, settings: FastinoSettings):
        self._settings = settings

    @classmethod
    def from_env(cls) -> "FastinoSafetyEngine":
        return cls(settings=FastinoSettings.from_env())

    def redact_sensitive_text(self, text: str) -> RedactionResult:
        clean_text = text or ""
        if not self._settings.enabled or not clean_text.strip():
            return RedactionResult(
                sanitized_text=clean_text,
                redactions=[],
                engine="disabled",
            )

        if not self._settings.api_key:
            return self._regex_redaction(clean_text, engine="local_fallback")

        try:
            response_payload = self._invoke_gliner(
                task="extract_entities",
                text=clean_text,
                schema=PII_SCHEMA,
                threshold=self._settings.pii_threshold,
            )
            entities = self._extract_entities(response_payload)
            if not entities:
                return self._regex_redaction(clean_text, engine="fastino_plus_local")
            return self._redact_with_entities(clean_text, entities, engine="fastino")
        except Exception as exc:
            fallback = self._regex_redaction(clean_text, engine="local_fallback")
            fallback.error = f"fastino_redaction_failed: {exc}"
            return fallback

    def evaluate_action(self, action_text: str) -> ActionCheckResult:
        clean_text = action_text or ""
        if not self._settings.enabled:
            return ActionCheckResult(
                allowed=True,
                category="guardrails_disabled",
                score=None,
                reason="Guardrails disabled by configuration.",
                engine="disabled",
            )

        if not self._settings.api_key:
            return self._local_action_check(clean_text, engine="local_fallback")

        try:
            payload = self._invoke_gliner(
                task="classify_text",
                text=clean_text,
                categories=ACTION_CATEGORIES,
                threshold=self._settings.action_threshold,
            )
            result = self._parse_classification(payload)
            if result is None:
                return self._local_action_check(clean_text, engine="fastino_plus_local")

            category, score = result
            blocked = category in BLOCKED_ACTION_CATEGORIES
            return ActionCheckResult(
                allowed=not blocked,
                category=category,
                score=score,
                reason=(
                    "Blocked by policy due to high-risk action."
                    if blocked
                    else "Action classified as safe."
                ),
                engine="fastino",
            )
        except Exception as exc:
            local = self._local_action_check(clean_text, engine="local_fallback")
            if self._settings.fail_mode == "closed" and local.allowed:
                local.allowed = False
                local.category = "guardrail_service_unavailable"
                local.reason = "Blocked because guardrail service is unavailable and fail mode is closed."
            local.error = f"fastino_classification_failed: {exc}"
            return local

    def _invoke_gliner(self, task: str, text: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self._settings.base_url}/gliner-2"
        headers = {
            "x-api-key": self._settings.api_key or "",
            "content-type": "application/json",
        }
        payload: dict[str, Any] = {
            "task": task,
            "input": text,
        }
        payload.update(kwargs)
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=self._settings.timeout_seconds,
        )
        response.raise_for_status()
        parsed = response.json()
        return parsed if isinstance(parsed, dict) else {"result": parsed}

    def _extract_entities(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        candidates = self._collect_entity_candidates(payload)
        entities: list[dict[str, str]] = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            value = self._pick_first_string(item, ["text", "value", "entity", "span"])
            label = self._pick_first_string(item, ["label", "type", "entity_type", "name"])
            if value:
                entities.append(
                    {
                        "text": value,
                        "label": (label or "sensitive").lower(),
                    }
                )
        return entities

    def _collect_entity_candidates(self, payload: Any) -> list[Any]:
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []

        for key in ("entities", "results", "predictions", "output", "data", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested = self._collect_entity_candidates(value)
                if nested:
                    return nested
        return []

    @staticmethod
    def _pick_first_string(data: dict[str, Any], keys: list[str]) -> str | None:
        for key in keys:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _redact_with_entities(
        self, text: str, entities: list[dict[str, str]], engine: str
    ) -> RedactionResult:
        redacted = text
        applied: list[dict[str, Any]] = []
        # Replace longer matches first to avoid partial replacement collisions.
        for item in sorted(entities, key=lambda x: len(x["text"]), reverse=True):
            token = item["text"].strip()
            if not token:
                continue
            placeholder = f"[REDACTED_{self._normalize_label(item['label'])}]"
            if token in redacted:
                redacted = redacted.replace(token, placeholder)
                applied.append({"label": item["label"], "placeholder": placeholder})
        return RedactionResult(
            sanitized_text=redacted,
            redactions=applied,
            engine=engine,
        )

    def _regex_redaction(self, text: str, engine: str) -> RedactionResult:
        rules: list[tuple[re.Pattern[str], str]] = [
            (EMAIL_PATTERN, "EMAIL_ADDRESS"),
            (PHONE_PATTERN, "PHONE_NUMBER"),
            (SSN_PATTERN, "SSN"),
            (CARD_PATTERN, "PAYMENT_CARD"),
            (BANK_PATTERN, "BANK_ACCOUNT"),
            (OPENAI_KEY_PATTERN, "OPENAI_KEY"),
            (AWS_KEY_PATTERN, "AWS_KEY"),
        ]

        redacted = text
        applied: list[dict[str, Any]] = []
        for pattern, label in rules:
            matches = list(pattern.finditer(redacted))
            if not matches:
                continue
            placeholder = f"[REDACTED_{label}]"
            redacted = pattern.sub(placeholder, redacted)
            applied.append({"label": label.lower(), "placeholder": placeholder, "count": len(matches)})

        return RedactionResult(
            sanitized_text=redacted,
            redactions=applied,
            engine=engine,
        )

    def _local_action_check(self, action_text: str, engine: str) -> ActionCheckResult:
        if DANGEROUS_ACTION_PATTERN.search(action_text):
            return ActionCheckResult(
                allowed=False,
                category="dangerous_financial_action",
                score=None,
                reason="Blocked because action matched dangerous-operation policy keywords.",
                engine=engine,
            )
        return ActionCheckResult(
            allowed=True,
            category="safe_operation",
            score=None,
            reason="No high-risk action pattern detected.",
            engine=engine,
        )

    def _parse_classification(self, payload: dict[str, Any]) -> tuple[str, float | None] | None:
        direct_label = self._pick_first_string(payload, ["label", "category", "class"])
        direct_score = self._pick_numeric(payload, ["score", "confidence", "probability"])
        if direct_label:
            return direct_label.lower(), direct_score

        results = self._collect_entity_candidates(payload)
        best_label: str | None = None
        best_score: float = -1.0
        for item in results:
            if not isinstance(item, dict):
                continue
            label = self._pick_first_string(item, ["label", "category", "class"])
            score = self._pick_numeric(item, ["score", "confidence", "probability"])
            if not label:
                continue
            normalized_score = score if score is not None else 0.0
            if normalized_score > best_score:
                best_score = normalized_score
                best_label = label.lower()

        if best_label is None:
            return None
        return best_label, (best_score if best_score >= 0 else None)

    @staticmethod
    def _pick_numeric(data: dict[str, Any], keys: list[str]) -> float | None:
        for key in keys:
            value = data.get(key)
            if isinstance(value, (int, float)):
                return float(value)
        return None

    @staticmethod
    def _normalize_label(label: str) -> str:
        value = re.sub(r"[^A-Za-z0-9]+", "_", label.strip().upper())
        return value or "SENSITIVE"
