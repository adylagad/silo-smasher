from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


@dataclass
class MemoryLoggerSettings:
    bucket_name: str | None
    prefix: str
    aws_region: str
    enabled: bool

    @classmethod
    def from_env(cls) -> "MemoryLoggerSettings":
        bucket_name = cls._clean(os.getenv("AWS_S3_MEMORY_BUCKET"))
        enabled_value = os.getenv("AWS_S3_MEMORY_ENABLED", "true").strip().lower()
        return cls(
            bucket_name=bucket_name,
            prefix=os.getenv("AWS_S3_MEMORY_PREFIX", "diagnostic-runs/").strip("/") + "/",
            aws_region=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")).strip(),
            enabled=enabled_value in {"1", "true", "yes", "on"},
        )

    @staticmethod
    def _clean(value: str | None) -> str | None:
        if not value:
            return None
        cleaned = value.strip()
        return None if cleaned in {"__MISSING__", "__SET_ME__"} else cleaned


class MemoryLogger:
    """Writes and reads diagnostic run memory logs in S3.

    Each run is stored at:
      s3://<bucket>/<prefix><YYYY>/<MM>/<DD>/<run_id>.json

    Falls back gracefully when S3 is not configured.
    """

    def __init__(self, settings: MemoryLoggerSettings):
        self._settings = settings
        self._client: Any = None
        if settings.enabled and settings.bucket_name:
            try:
                self._client = boto3.client("s3", region_name=settings.aws_region)
            except Exception:
                self._client = None

    @classmethod
    def from_env(cls) -> "MemoryLogger":
        return cls(settings=MemoryLoggerSettings.from_env())

    @property
    def is_active(self) -> bool:
        return self._client is not None and bool(self._settings.bucket_name)

    def log_run(
        self,
        *,
        run_id: str,
        question: str,
        result: dict[str, Any],
    ) -> str | None:
        """Persist a diagnostic run to S3. Returns the S3 key or None."""
        if not self.is_active:
            return None

        now = datetime.now(timezone.utc)
        key = (
            f"{self._settings.prefix}"
            f"{now.year}/{now.month:02d}/{now.day:02d}/{run_id}.json"
        )
        log_entry: dict[str, Any] = {
            "run_id": run_id,
            "timestamp": now.isoformat(),
            "question": question,
            "result": result,
        }
        try:
            self._client.put_object(
                Bucket=self._settings.bucket_name,
                Key=key,
                Body=json.dumps(log_entry, indent=2, sort_keys=True, ensure_ascii=True).encode(),
                ContentType="application/json",
            )
            return key
        except (BotoCoreError, ClientError):
            return None

    def list_recent_runs(self, max_keys: int = 20) -> list[dict[str, Any]]:
        """Return metadata for the most recent memory-log objects in S3."""
        if not self.is_active:
            return []
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            pages = paginator.paginate(
                Bucket=self._settings.bucket_name,
                Prefix=self._settings.prefix,
                PaginationConfig={"MaxItems": max_keys},
            )
            items: list[dict[str, Any]] = []
            for page in pages:
                for obj in page.get("Contents", []):
                    items.append(
                        {
                            "key": obj["Key"],
                            "last_modified": obj["LastModified"].isoformat()
                            if hasattr(obj["LastModified"], "isoformat")
                            else str(obj["LastModified"]),
                            "size_bytes": obj["Size"],
                        }
                    )
            items.sort(key=lambda x: x["last_modified"], reverse=True)
            return items[:max_keys]
        except (BotoCoreError, ClientError):
            return []

    def get_run(self, key: str) -> dict[str, Any] | None:
        """Fetch a single memory-log entry by its S3 key."""
        if not self.is_active:
            return None
        try:
            response = self._client.get_object(
                Bucket=self._settings.bucket_name,
                Key=key,
            )
            body = response["Body"].read().decode("utf-8")
            return json.loads(body)
        except (BotoCoreError, ClientError, json.JSONDecodeError):
            return None
