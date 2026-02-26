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
