from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class MonitoringSettings:
    default_interval_seconds: int
    min_interval_seconds: int
    max_interval_seconds: int
    notifications_enabled: bool
    slack_webhook_url: str | None
    ses_sender_email: str | None
    ses_recipient_email: str | None
    aws_region: str

    @classmethod
    def from_env(cls) -> "MonitoringSettings":
        notifications_enabled_value = os.getenv(
            "MONITOR_NOTIFICATIONS_ENABLED", "true"
        ).strip().lower()
        return cls(
            default_interval_seconds=max(
                5, int(os.getenv("MONITOR_DEFAULT_INTERVAL_SECONDS", "300"))
            ),
            min_interval_seconds=max(
                1, int(os.getenv("MONITOR_MIN_INTERVAL_SECONDS", "30"))
            ),
            max_interval_seconds=max(
                5, int(os.getenv("MONITOR_MAX_INTERVAL_SECONDS", "3600"))
            ),
            notifications_enabled=notifications_enabled_value in {"1", "true", "yes", "on"},
            slack_webhook_url=cls._clean(os.getenv("MONITOR_SLACK_WEBHOOK_URL")),
            ses_sender_email=cls._clean(os.getenv("MONITOR_SES_FROM_EMAIL")),
            ses_recipient_email=cls._clean(os.getenv("MONITOR_SES_TO_EMAIL")),
            aws_region=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")).strip(),
        )

    @staticmethod
    def _clean(value: str | None) -> str | None:
        if not value:
            return None
        cleaned = value.strip()
        if cleaned in {"__MISSING__", "__SET_ME__"}:
            return None
        return cleaned
