from __future__ import annotations

import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from silo_smasher.memory import MemoryLogger
from silo_smasher.orchestrator import (
    DiagnosticOrchestrator,
    OrchestratorSettings,
)

from .models import (
    DiagnoseRequest,
    PipelineStartRequest,
    PipelineStartResponse,
    PipelineStatusResponse,
)

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.orchestrator = DiagnosticOrchestrator(OrchestratorSettings.from_env())
    app.state.memory_logger = MemoryLogger.from_env()
    yield


app = FastAPI(
    title="Autonomous Diagnostic Engine",
    description=(
        "Graph-Augmented Agentic BI — cross-silo root-cause investigator. "
        "Correlates structured DB data, internal graph context, and external signals "
        "to answer *why* a business metric changed."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the React frontend — prefer the Vite build output (frontend/dist/),
# fall back to the raw frontend/ directory for local dev without a build step.
import pathlib as _pathlib
_frontend_dir = _pathlib.Path(__file__).parent.parent / "frontend" / "dist"
if not _frontend_dir.is_dir():
    _frontend_dir = _pathlib.Path(__file__).parent.parent / "frontend"
if _frontend_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_frontend_dir / "assets")), name="assets") if (_frontend_dir / "assets").is_dir() else None
    app.mount("/app", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    return FileResponse(str(_frontend_dir / "index.html"))


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Infra"])
def health() -> dict[str, Any]:
    logger: MemoryLogger = app.state.memory_logger
    return {
        "status": "ok",
        "s3_memory_active": logger.is_active,
        "step_functions_arn": os.getenv("AWS_STEP_FUNCTIONS_STATE_MACHINE_ARN") or None,
    }


# ---------------------------------------------------------------------------
# Synchronous diagnosis (OpenAI → Gemini fallback → local fallback)
# ---------------------------------------------------------------------------

@app.post("/diagnose", tags=["Diagnosis"])
def diagnose(request: DiagnoseRequest) -> dict[str, Any]:
    """Run the full agentic diagnostic loop and return the root-cause brief.

    The orchestrator:
    1. Generates hypotheses.
    2. Uses tools (SQL, Neo4j GraphRAG, internal communications, Senso, Numeric, Tavily, Modulate, Yutori) to test them.
    3. Returns a structured executive brief with confidence scores.

    The result is also persisted to S3 as a memory-log entry.
    """
    orchestrator: DiagnosticOrchestrator = app.state.orchestrator
    memory_logger: MemoryLogger = app.state.memory_logger

    result = orchestrator.run(
        question=request.question,
        extra_context=request.extra_context,
    )

    run_id = str(uuid.uuid4())
    s3_key = memory_logger.log_run(
        run_id=run_id,
        question=request.question,
        result=result,
    )

    result["run_id"] = run_id
    result["s3_memory_key"] = s3_key
    return result


# ---------------------------------------------------------------------------
# Memory log endpoints (S3)
# ---------------------------------------------------------------------------

@app.get("/memory", tags=["Memory"])
def list_memory_runs(limit: int = 20) -> dict[str, Any]:
    """List recent diagnostic runs stored in S3 memory logs."""
    memory_logger: MemoryLogger = app.state.memory_logger
    if not memory_logger.is_active:
        return {
            "runs": [],
            "message": "S3 memory logging is not configured. Set AWS_S3_MEMORY_BUCKET.",
        }
    runs = memory_logger.list_recent_runs(max_keys=min(limit, 100))
    return {"runs": runs, "count": len(runs)}


@app.get("/memory/{s3_key:path}", tags=["Memory"])
def get_memory_run(s3_key: str) -> dict[str, Any]:
    """Fetch a specific diagnostic run from the S3 memory log."""
    memory_logger: MemoryLogger = app.state.memory_logger
    if not memory_logger.is_active:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="S3 memory logging is not configured. Set AWS_S3_MEMORY_BUCKET.",
        )
    entry = memory_logger.get_run(s3_key)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory log entry not found: {s3_key}",
        )
    return entry


# ---------------------------------------------------------------------------
# Async pipeline (AWS Step Functions)
# ---------------------------------------------------------------------------

def _sfn_client() -> Any:
    return boto3.client(
        "stepfunctions",
        region_name=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")),
    )


@app.post("/pipeline", response_model=PipelineStartResponse, tags=["Pipeline"])
def start_pipeline(request: PipelineStartRequest) -> PipelineStartResponse:
    """Trigger the full multi-step pipeline via AWS Step Functions.

    The state machine runs these steps in sequence:
    1. IngestData   — pull fresh records from Airbyte (or skip to local file).
    2. BuildContext — normalize records into agent-ready context JSON.
    3. SyncGraph    — push context to Neo4j AuraDB (GraphRAG).
    4. RunDiagnosis — execute the agentic orchestrator on the question.
    5. LogMemory    — persist the result to S3.

    Returns an `execution_arn` you can poll with GET /pipeline/{execution_arn}.
    """
    state_machine_arn = os.getenv("AWS_STEP_FUNCTIONS_STATE_MACHINE_ARN", "").strip()
    if not state_machine_arn:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "AWS_STEP_FUNCTIONS_STATE_MACHINE_ARN is not set. "
                "Deploy the state machine first (see aws/step_functions/)."
            ),
        )

    execution_input = json.dumps(
        {
            "question": request.question,
            "source_name": request.source_name,
            "record_count": request.record_count,
            "seed": request.seed,
            "input_json_path": request.input_json_path,
        },
        ensure_ascii=True,
    )

    try:
        sfn = _sfn_client()
        response = sfn.start_execution(
            stateMachineArn=state_machine_arn,
            input=execution_input,
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to start Step Functions execution: {exc}",
        ) from exc

    started_at = response["startDate"]
    return PipelineStartResponse(
        execution_arn=response["executionArn"],
        started_at=started_at.isoformat() if hasattr(started_at, "isoformat") else str(started_at),
    )


@app.get("/pipeline/{execution_arn:path}", response_model=PipelineStatusResponse, tags=["Pipeline"])
def get_pipeline_status(execution_arn: str) -> PipelineStatusResponse:
    """Poll the status of a running or completed Step Functions execution."""
    try:
        sfn = _sfn_client()
        response = sfn.describe_execution(executionArn=execution_arn)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code == "ExecutionDoesNotExist":
            raise HTTPException(status_code=404, detail="Execution not found.")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except BotoCoreError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    output: dict[str, Any] | None = None
    if response.get("output"):
        try:
            output = json.loads(response["output"])
        except (json.JSONDecodeError, TypeError):
            output = {"raw": response.get("output")}

    start = response.get("startDate")
    stop = response.get("stopDate")
    return PipelineStatusResponse(
        execution_arn=execution_arn,
        status=response["status"],
        started_at=start.isoformat() if hasattr(start, "isoformat") else str(start) if start else None,
        stopped_at=stop.isoformat() if hasattr(stop, "isoformat") else str(stop) if stop else None,
        output=output,
    )
