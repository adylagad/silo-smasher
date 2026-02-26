from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DiagnoseRequest(BaseModel):
    question: str = Field(..., description="The diagnostic question to investigate.")
    extra_context: str | None = Field(
        None,
        description="Optional raw text or JSON to include as extra grounding context.",
    )


class PipelineStartRequest(BaseModel):
    question: str = Field(..., description="Diagnostic question the pipeline should answer.")
    source_name: str = Field("synthetic-catalog-source", description="Airbyte source name.")
    record_count: int = Field(1000, ge=1, le=100_000, description="Synthetic record count.")
    seed: int = Field(42, description="RNG seed for reproducible synthetic data.")
    input_json_path: str | None = Field(
        None,
        description="Local JSON bundle path used by BuildContext when Airbyte is not configured.",
    )


class PipelineStartResponse(BaseModel):
    execution_arn: str
    started_at: str


class PipelineStatusResponse(BaseModel):
    execution_arn: str
    status: str
    started_at: str | None = None
    stopped_at: str | None = None
    output: dict[str, Any] | None = None


class MonitorStartRequest(BaseModel):
    metric_name: str = Field(
        ...,
        description=(
            "Metric to monitor for downward change. Supported: "
            "net_revenue, gross_revenue, purchased_count, returned_count, conversion_rate, return_rate."
        ),
    )
    drop_threshold_pct: float = Field(
        ...,
        description="Drop threshold as fraction (0.15) or percent (15) before auto-triggering diagnosis.",
    )
    check_interval_seconds: int | None = Field(
        None,
        description="How frequently to evaluate the metric. Clamped to monitor min/max env limits.",
    )
    comparison_window_hours: int = Field(
        24,
        ge=1,
        le=24 * 30,
        description="Current window size in hours.",
    )
    baseline_window_hours: int = Field(
        24,
        ge=1,
        le=24 * 30,
        description="Previous baseline window size in hours.",
    )
    auto_stop_after_trigger: bool = Field(
        False,
        description="Stop this monitor immediately after first triggered diagnosis.",
    )
    question_template: str | None = Field(
        None,
        description=(
            "Optional template for the diagnosis prompt. Supports "
            "{metric_name}, {drop_pct}, {current_value}, {baseline_value}, "
            "{comparison_window_hours}, {baseline_window_hours}."
        ),
    )
    extra_context: str | None = Field(
        None,
        description="Optional extra context attached to auto-triggered diagnosis.",
    )


class MonitorRecordResponse(BaseModel):
    monitor_id: str
    status: str
    config: dict[str, Any]
    runtime: dict[str, Any]


class MonitorListResponse(BaseModel):
    monitors: list[MonitorRecordResponse]
    count: int
