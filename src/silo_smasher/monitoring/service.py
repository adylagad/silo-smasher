from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import boto3
import requests
from botocore.exceptions import BotoCoreError, ClientError

from silo_smasher.structured_query import (
    StructuredQuerySettings,
    StructuredQueryStore,
    bootstrap_sqlite_from_artifacts,
)

from .config import MonitoringSettings

TriggerDiagnosisFn = Callable[[str, str | None], dict[str, Any]]

_METRIC_ALIASES = {
    "mrr": "net_revenue",
    "revenue": "net_revenue",
    "sales": "net_revenue",
}
_SUPPORTED_METRICS = {
    "net_revenue",
    "gross_revenue",
    "purchased_count",
    "returned_count",
    "conversion_rate",
    "return_rate",
}


@dataclass
class MonitorDefinition:
    monitor_id: str
    metric_name: str
    drop_threshold_pct: float
    check_interval_seconds: int
    comparison_window_hours: int
    baseline_window_hours: int
    auto_stop_after_trigger: bool
    question_template: str | None
    extra_context: str | None
    created_at: str


@dataclass
class MonitorState:
    status: str = "running"
    last_checked_at: str | None = None
    next_check_due_at: str | None = None
    last_error: str | None = None
    last_snapshot: dict[str, Any] | None = None
    trigger_count: int = 0
    last_triggered_at: str | None = None
    last_trigger_result: dict[str, Any] | None = None
    breach_active_last_check: bool = False
    notifications: list[dict[str, Any]] = field(default_factory=list)
    task: asyncio.Task[None] | None = None


@dataclass
class MonitorJob:
    definition: MonitorDefinition
    state: MonitorState

    def as_dict(self) -> dict[str, Any]:
        return {
            "monitor_id": self.definition.monitor_id,
            "status": self.state.status,
            "config": {
                "metric_name": self.definition.metric_name,
                "drop_threshold_pct": self.definition.drop_threshold_pct,
                "check_interval_seconds": self.definition.check_interval_seconds,
                "comparison_window_hours": self.definition.comparison_window_hours,
                "baseline_window_hours": self.definition.baseline_window_hours,
                "auto_stop_after_trigger": self.definition.auto_stop_after_trigger,
                "question_template": self.definition.question_template,
                "created_at": self.definition.created_at,
            },
            "runtime": {
                "last_checked_at": self.state.last_checked_at,
                "next_check_due_at": self.state.next_check_due_at,
                "last_error": self.state.last_error,
                "last_snapshot": self.state.last_snapshot,
                "trigger_count": self.state.trigger_count,
                "last_triggered_at": self.state.last_triggered_at,
                "last_trigger_result": self.state.last_trigger_result,
                "notifications": list(self.state.notifications[-10:]),
            },
        }


class MetricMonitorService:
    def __init__(
        self,
        *,
        settings: MonitoringSettings,
        trigger_diagnosis: TriggerDiagnosisFn,
    ) -> None:
        self._settings = settings
        self._trigger_diagnosis = trigger_diagnosis
        self._jobs: dict[str, MonitorJob] = {}
        self._lock = asyncio.Lock()
        self._structured_query_settings = StructuredQuerySettings.from_env()
        self._query_store = StructuredQueryStore(self._structured_query_settings.sqlite_path)
        self._bootstrap_state: dict[str, Any] | None = None

    @property
    def supported_metrics(self) -> list[str]:
        return sorted(_SUPPORTED_METRICS)

    async def shutdown(self) -> None:
        async with self._lock:
            jobs = list(self._jobs.values())
            self._jobs.clear()

        for job in jobs:
            task = job.state.task
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def start_monitor(
        self,
        *,
        metric_name: str,
        drop_threshold_pct: float,
        check_interval_seconds: int | None = None,
        comparison_window_hours: int = 24,
        baseline_window_hours: int = 24,
        auto_stop_after_trigger: bool = False,
        question_template: str | None = None,
        extra_context: str | None = None,
    ) -> dict[str, Any]:
        canonical_metric = self._canonical_metric_name(metric_name)
        threshold = self._normalize_threshold(drop_threshold_pct)
        interval = self._normalize_interval(check_interval_seconds)

        comparison_hours = max(1, int(comparison_window_hours))
        baseline_hours = max(1, int(baseline_window_hours))

        monitor_id = str(uuid.uuid4())
        now_iso = _utc_now_iso()
        job = MonitorJob(
            definition=MonitorDefinition(
                monitor_id=monitor_id,
                metric_name=canonical_metric,
                drop_threshold_pct=threshold,
                check_interval_seconds=interval,
                comparison_window_hours=comparison_hours,
                baseline_window_hours=baseline_hours,
                auto_stop_after_trigger=bool(auto_stop_after_trigger),
                question_template=question_template.strip() if question_template else None,
                extra_context=extra_context.strip() if extra_context else None,
                created_at=now_iso,
            ),
            state=MonitorState(
                status="running",
                next_check_due_at=now_iso,
            ),
        )

        async with self._lock:
            self._jobs[monitor_id] = job
            job.state.task = asyncio.create_task(
                self._run_monitor_loop(monitor_id),
                name=f"monitor-{monitor_id[:8]}",
            )
        return job.as_dict()

    async def list_monitors(self) -> list[dict[str, Any]]:
        async with self._lock:
            jobs = list(self._jobs.values())
        return [job.as_dict() for job in jobs]

    async def get_monitor(self, monitor_id: str) -> dict[str, Any]:
        async with self._lock:
            job = self._jobs.get(monitor_id)
            if not job:
                raise KeyError(monitor_id)
            return job.as_dict()

    async def stop_monitor(self, monitor_id: str) -> dict[str, Any]:
        async with self._lock:
            job = self._jobs.get(monitor_id)
            if not job:
                raise KeyError(monitor_id)
            job.state.status = "stopped"
            task = job.state.task

        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        return await self.get_monitor(monitor_id)

    async def run_check_once(self, monitor_id: str) -> dict[str, Any]:
        async with self._lock:
            job = self._jobs.get(monitor_id)
            if not job:
                raise KeyError(monitor_id)
        await self._evaluate_and_maybe_trigger(job)
        return await self.get_monitor(monitor_id)

    async def _run_monitor_loop(self, monitor_id: str) -> None:
        while True:
            async with self._lock:
                job = self._jobs.get(monitor_id)
                if job is None:
                    return
                if job.state.status != "running":
                    return
                interval = job.definition.check_interval_seconds

            await self._evaluate_and_maybe_trigger(job)

            async with self._lock:
                still_running = (
                    monitor_id in self._jobs
                    and self._jobs[monitor_id].state.status == "running"
                )
            if not still_running:
                return
            await asyncio.sleep(interval)

    async def _evaluate_and_maybe_trigger(self, job: MonitorJob) -> None:
        monitor_id = job.definition.monitor_id
        try:
            snapshot = await asyncio.to_thread(
                self._build_snapshot,
                job.definition,
            )
            should_trigger = bool(snapshot.get("is_breached", False)) and not job.state.breach_active_last_check

            now_iso = _utc_now_iso()
            async with self._lock:
                live_job = self._jobs.get(monitor_id)
                if live_job is None:
                    return
                live_job.state.last_checked_at = now_iso
                live_job.state.last_error = None
                live_job.state.last_snapshot = snapshot
                live_job.state.breach_active_last_check = bool(snapshot.get("is_breached", False))
                if live_job.state.status == "running":
                    live_job.state.next_check_due_at = _utc_iso_after_seconds(
                        live_job.definition.check_interval_seconds
                    )

            if should_trigger:
                question = self._build_question(job.definition, snapshot)
                extra_context = self._build_extra_context(job.definition, snapshot)
                diagnosis = await asyncio.to_thread(
                    self._trigger_diagnosis,
                    question,
                    extra_context,
                )
                notification_result = await asyncio.to_thread(
                    self._dispatch_notifications,
                    monitor_id,
                    question,
                    snapshot,
                    diagnosis,
                )

                async with self._lock:
                    live_job = self._jobs.get(monitor_id)
                    if live_job is None:
                        return
                    live_job.state.trigger_count += 1
                    live_job.state.last_triggered_at = _utc_now_iso()
                    live_job.state.last_trigger_result = {
                        "run_id": diagnosis.get("run_id"),
                        "s3_memory_key": diagnosis.get("s3_memory_key"),
                        "provider": diagnosis.get("_provider"),
                        "most_likely_root_cause": diagnosis.get("most_likely_root_cause"),
                        "confidence_overall": diagnosis.get("confidence_overall"),
                    }
                    live_job.state.notifications.append(notification_result)

                    if live_job.definition.auto_stop_after_trigger:
                        live_job.state.status = "stopped_after_trigger"
                        live_job.state.next_check_due_at = None
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            async with self._lock:
                live_job = self._jobs.get(monitor_id)
                if live_job is None:
                    return
                live_job.state.last_checked_at = _utc_now_iso()
                live_job.state.last_error = str(exc)
                live_job.state.next_check_due_at = _utc_iso_after_seconds(
                    live_job.definition.check_interval_seconds
                )

    def _build_snapshot(self, definition: MonitorDefinition) -> dict[str, Any]:
        self._ensure_sqlite_data()
        now = datetime.now(timezone.utc)
        current_end = now
        current_start = current_end - timedelta(hours=definition.comparison_window_hours)
        baseline_end = current_start
        baseline_start = baseline_end - timedelta(hours=definition.baseline_window_hours)

        current_value = self._metric_value(
            definition.metric_name,
            start=current_start,
            end=current_end,
        )
        baseline_value = self._metric_value(
            definition.metric_name,
            start=baseline_start,
            end=baseline_end,
        )

        drop_pct = 0.0
        trend = "flat"
        if baseline_value > 0:
            drop_pct = (baseline_value - current_value) / baseline_value
            if drop_pct > 0:
                trend = "down"
            elif drop_pct < 0:
                trend = "up"

        is_breached = baseline_value > 0 and drop_pct >= definition.drop_threshold_pct
        return {
            "metric_name": definition.metric_name,
            "current_value": round(current_value, 6),
            "baseline_value": round(baseline_value, 6),
            "drop_pct": round(drop_pct, 6),
            "threshold_pct": definition.drop_threshold_pct,
            "is_breached": is_breached,
            "trend": trend,
            "comparison_window_hours": definition.comparison_window_hours,
            "baseline_window_hours": definition.baseline_window_hours,
            "windows": {
                "current_start": _to_iso(current_start),
                "current_end": _to_iso(current_end),
                "baseline_start": _to_iso(baseline_start),
                "baseline_end": _to_iso(baseline_end),
            },
            "bootstrap_state": self._bootstrap_state,
        }

    def _metric_value(self, metric_name: str, *, start: datetime, end: datetime) -> float:
        params = {"start": _to_iso(start), "end": _to_iso(end)}
        if metric_name == "net_revenue":
            return self._scalar(
                """
                SELECT COALESCE(SUM(pr.price), 0.0) AS value
                FROM purchases p
                JOIN products pr ON pr.id = p.product_id
                WHERE p.purchased_at IS NOT NULL
                  AND p.returned_at IS NULL
                  AND p.purchased_at >= :start
                  AND p.purchased_at < :end
                """,
                params,
            )
        if metric_name == "gross_revenue":
            return self._scalar(
                """
                SELECT COALESCE(SUM(pr.price), 0.0) AS value
                FROM purchases p
                JOIN products pr ON pr.id = p.product_id
                WHERE p.purchased_at IS NOT NULL
                  AND p.purchased_at >= :start
                  AND p.purchased_at < :end
                """,
                params,
            )
        if metric_name == "purchased_count":
            return self._scalar(
                """
                SELECT COUNT(*) AS value
                FROM purchases
                WHERE purchased_at IS NOT NULL
                  AND purchased_at >= :start
                  AND purchased_at < :end
                """,
                params,
            )
        if metric_name == "returned_count":
            return self._scalar(
                """
                SELECT COUNT(*) AS value
                FROM purchases
                WHERE returned_at IS NOT NULL
                  AND returned_at >= :start
                  AND returned_at < :end
                """,
                params,
            )
        if metric_name == "conversion_rate":
            purchased = self._scalar(
                """
                SELECT COUNT(*) AS value
                FROM purchases
                WHERE purchased_at IS NOT NULL
                  AND purchased_at >= :start
                  AND purchased_at < :end
                """,
                params,
            )
            cart_intent = self._scalar(
                """
                SELECT COUNT(*) AS value
                FROM purchases
                WHERE added_to_cart_at IS NOT NULL
                  AND added_to_cart_at >= :start
                  AND added_to_cart_at < :end
                """,
                params,
            )
            return 0.0 if cart_intent <= 0 else purchased / cart_intent
        if metric_name == "return_rate":
            purchased = self._scalar(
                """
                SELECT COUNT(*) AS value
                FROM purchases
                WHERE purchased_at IS NOT NULL
                  AND purchased_at >= :start
                  AND purchased_at < :end
                """,
                params,
            )
            returned = self._scalar(
                """
                SELECT COUNT(*) AS value
                FROM purchases
                WHERE returned_at IS NOT NULL
                  AND returned_at >= :start
                  AND returned_at < :end
                """,
                params,
            )
            return 0.0 if purchased <= 0 else returned / purchased
        raise RuntimeError(f"Unsupported metric: {metric_name}")

    def _scalar(self, sql: str, params: dict[str, Any]) -> float:
        result = self._query_store.execute_read_query(
            sql=sql,
            params=params,
            max_rows=1,
            max_rows_limit=1,
        )
        rows = result.get("rows", [])
        if not rows:
            return 0.0
        value = rows[0].get("value")
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _ensure_sqlite_data(self) -> None:
        if self._query_store.has_data():
            return
        self._bootstrap_state = bootstrap_sqlite_from_artifacts(self._query_store)

    def _canonical_metric_name(self, metric_name: str) -> str:
        candidate = str(metric_name or "").strip().lower()
        if not candidate:
            raise ValueError("metric_name is required")
        candidate = _METRIC_ALIASES.get(candidate, candidate)
        if candidate not in _SUPPORTED_METRICS:
            raise ValueError(
                f"Unsupported metric_name '{metric_name}'. Supported: {', '.join(sorted(_SUPPORTED_METRICS))}"
            )
        return candidate

    def _normalize_threshold(self, threshold: float) -> float:
        value = float(threshold)
        if value <= 0:
            raise ValueError("drop_threshold_pct must be > 0")
        if value > 1:
            value = value / 100.0
        if value >= 1:
            raise ValueError("drop_threshold_pct must be less than 100%")
        return value

    def _normalize_interval(self, interval: int | None) -> int:
        candidate = (
            self._settings.default_interval_seconds
            if interval is None
            else int(interval)
        )
        if candidate < self._settings.min_interval_seconds:
            return self._settings.min_interval_seconds
        if candidate > self._settings.max_interval_seconds:
            return self._settings.max_interval_seconds
        return candidate

    def _build_question(self, definition: MonitorDefinition, snapshot: dict[str, Any]) -> str:
        metric = snapshot.get("metric_name", definition.metric_name)
        drop_pct = float(snapshot.get("drop_pct", 0.0)) * 100
        current_value = snapshot.get("current_value", 0.0)
        baseline_value = snapshot.get("baseline_value", 0.0)
        default_prompt = (
            f"Metric alert: {metric} dropped by {drop_pct:.1f}% "
            f"(baseline={baseline_value}, current={current_value}) over the last "
            f"{definition.comparison_window_hours} hours. Diagnose why this changed."
        )
        if not definition.question_template:
            return default_prompt
        try:
            return definition.question_template.format(
                metric_name=metric,
                drop_pct=drop_pct,
                current_value=current_value,
                baseline_value=baseline_value,
                comparison_window_hours=definition.comparison_window_hours,
                baseline_window_hours=definition.baseline_window_hours,
            )
        except Exception:  # noqa: BLE001
            return default_prompt

    def _build_extra_context(self, definition: MonitorDefinition, snapshot: dict[str, Any]) -> str:
        payload: dict[str, Any] = {
            "trigger_type": "proactive_metric_monitor",
            "monitor_id": definition.monitor_id,
            "monitor_config": {
                "metric_name": definition.metric_name,
                "drop_threshold_pct": definition.drop_threshold_pct,
                "check_interval_seconds": definition.check_interval_seconds,
                "comparison_window_hours": definition.comparison_window_hours,
                "baseline_window_hours": definition.baseline_window_hours,
            },
            "snapshot": snapshot,
        }
        if definition.extra_context:
            payload["user_context"] = definition.extra_context
        return json.dumps(payload, ensure_ascii=True)

    def _dispatch_notifications(
        self,
        monitor_id: str,
        question: str,
        snapshot: dict[str, Any],
        diagnosis: dict[str, Any],
    ) -> dict[str, Any]:
        timestamp = _utc_now_iso()
        result: dict[str, Any] = {
            "timestamp": timestamp,
            "monitor_id": monitor_id,
            "notifications_enabled": self._settings.notifications_enabled,
            "slack": {"status": "skipped", "reason": "not_configured"},
            "email": {"status": "skipped", "reason": "not_configured"},
        }

        if not self._settings.notifications_enabled:
            result["slack"] = {"status": "skipped", "reason": "notifications_disabled"}
            result["email"] = {"status": "skipped", "reason": "notifications_disabled"}
            return result

        metric_name = snapshot.get("metric_name")
        drop_pct = float(snapshot.get("drop_pct", 0.0)) * 100
        root_cause = diagnosis.get("most_likely_root_cause") or "No root cause returned."
        run_id = diagnosis.get("run_id")
        summary_line = (
            f"[Monitor Alert] {metric_name} dropped {drop_pct:.1f}% | run_id={run_id or 'n/a'}"
        )

        if self._settings.slack_webhook_url:
            try:
                payload = {
                    "text": (
                        f"{summary_line}\n"
                        f"Question: {question}\n"
                        f"Root cause: {root_cause}"
                    )
                }
                response = requests.post(
                    self._settings.slack_webhook_url,
                    json=payload,
                    timeout=10,
                )
                if 200 <= response.status_code < 300:
                    result["slack"] = {"status": "sent", "status_code": response.status_code}
                else:
                    result["slack"] = {
                        "status": "failed",
                        "status_code": response.status_code,
                        "detail": response.text[:200],
                    }
            except requests.RequestException as exc:
                result["slack"] = {"status": "failed", "detail": str(exc)}

        if self._settings.ses_sender_email and self._settings.ses_recipient_email:
            try:
                ses = boto3.client("ses", region_name=self._settings.aws_region)
                ses.send_email(
                    Source=self._settings.ses_sender_email,
                    Destination={"ToAddresses": [self._settings.ses_recipient_email]},
                    Message={
                        "Subject": {"Data": summary_line},
                        "Body": {
                            "Text": {
                                "Data": (
                                    f"{summary_line}\n\n"
                                    f"Question: {question}\n"
                                    f"Root cause: {root_cause}\n"
                                    f"Confidence: {diagnosis.get('confidence_overall')}\n"
                                    f"S3 key: {diagnosis.get('s3_memory_key')}\n"
                                )
                            }
                        },
                    },
                )
                result["email"] = {"status": "sent"}
            except (BotoCoreError, ClientError) as exc:
                result["email"] = {"status": "failed", "detail": str(exc)}

        return result


def _to_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _utc_now_iso() -> str:
    return _to_iso(datetime.now(timezone.utc))


def _utc_iso_after_seconds(seconds: int) -> str:
    return _to_iso(datetime.now(timezone.utc) + timedelta(seconds=max(1, int(seconds))))
