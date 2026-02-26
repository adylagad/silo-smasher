"""AWS Lambda handlers for the Autonomous Diagnostic Pipeline.

Each function maps to one Step Functions state. Deploy each as a separate
Lambda function (all share the same package/layer).

Handler names used in the AWS Lambda console / state_machine.json
(set Handler = pipeline_handlers.<function>):
  pipeline_handlers.ingest_data
  pipeline_handlers.build_agent_context
  pipeline_handlers.sync_graph_context
  pipeline_handlers.run_diagnosis
  pipeline_handlers.log_memory

Directory: aws/handlers/pipeline_handlers.py
  ("lambda" is a Python reserved word, so the directory is named "handlers".)

Environment variables are loaded from the Lambda runtime environment.
Mirror the variables in your .env.example when configuring the functions.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

# Lambda adds /var/task to sys.path; the package must be installed in the layer.
# For local testing: pip install -e . from the repo root.
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# State 1: IngestData
# ---------------------------------------------------------------------------

def ingest_data(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Pull fresh synthetic records from Airbyte.

    Expected event keys (all optional):
      source_name     str   — Airbyte source name.
      record_count    int   — number of records to generate.
      seed            int   — RNG seed.

    Returns:
      status          str
      source_name     str
      input_json_path str   — path to the raw JSON file for BuildContext.
    """
    source_name = str(event.get("source_name", "synthetic-catalog-source"))
    record_count = int(event.get("record_count", 1000))
    seed = int(event.get("seed", 42))

    airbyte_url = os.getenv("AIRBYTE_SERVER_URL", "").strip()
    has_airbyte = bool(airbyte_url and airbyte_url != "http://localhost:8000/api/public/v1")

    if not has_airbyte:
        # Use the pre-existing local example bundle.
        local_path = str(
            Path(os.getenv("LAMBDA_TASK_ROOT", ".")) / "examples" / "synthetic_raw_bundle.json"
        )
        return {
            "status": "skipped_airbyte_not_configured",
            "source_name": source_name,
            "input_json_path": event.get("input_json_path") or local_path,
        }

    try:
        from silo_smasher.synthetic_sync import (
            _build_client,
            _ensure_source,
            _pick_workspace_id,
        )

        client = _build_client()
        workspace_id = _pick_workspace_id(client, os.getenv("AIRBYTE_WORKSPACE_ID"))
        source = _ensure_source(
            client=client,
            workspace_id=workspace_id,
            source_definition_id=os.getenv("AIRBYTE_SOURCE_DEFINITION_ID"),
            source_name=source_name,
            count=record_count,
            seed=seed,
        )
        return {
            "status": "source_ready",
            "source_name": source.name,
            "source_id": source.source_id,
            "workspace_id": workspace_id,
            "input_json_path": event.get("input_json_path"),
        }
    except Exception as exc:
        return {
            "status": "airbyte_error",
            "error": str(exc),
            "source_name": source_name,
            "input_json_path": event.get("input_json_path"),
        }


# ---------------------------------------------------------------------------
# State 2: BuildAgentContext
# ---------------------------------------------------------------------------

def build_agent_context(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Normalize raw records into agent-ready context JSON.

    Reads from:
      event.ingest.ingest_result.input_json_path   (from IngestData state)
      event.input_json_path                         (direct override)

    Returns context_path and manifest_path.
    """
    from silo_smasher.pipeline import run_ground_truth_pipeline

    ingest = (event.get("ingest") or {}).get("ingest_result") or {}
    input_path_str = (
        ingest.get("input_json_path")
        or event.get("input_json_path")
        or str(Path(os.getenv("LAMBDA_TASK_ROOT", ".")) / "examples" / "synthetic_raw_bundle.json")
    )
    input_path = Path(input_path_str)
    if not input_path.exists():
        return {"status": "error", "error": f"input_json_path not found: {input_path}"}

    tmp_root = Path(os.getenv("LAMBDA_TMP_ROOT", "/tmp")) / "system_of_record"
    try:
        summary = run_ground_truth_pipeline(
            input_path=input_path,
            output_root=tmp_root,
            source_name=str(event.get("source_name", "lambda_synthetic_source")),
            workspace_id=None,
            connection_id=None,
            publish_to_senso=False,
            senso_title_prefix="Lambda Synthetic",
        )
        return {"status": "ok", **summary}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# State 3: SyncGraphContext
# ---------------------------------------------------------------------------

def sync_graph_context(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Push the normalized context into Neo4j AuraDB.

    Reads:
      event.context.context_result.context_path   (from BuildAgentContext)
    """
    from silo_smasher.graph import GraphRAGService, GraphSettings, Neo4jGraphStore
    from silo_smasher.graph.bedrock_embedder import BedrockEmbedder

    ctx_result = (event.get("context") or {}).get("context_result") or {}
    context_path_str = ctx_result.get("context_path") or event.get("context_path")
    if not context_path_str:
        return {"status": "error", "error": "context_path not provided by BuildAgentContext"}

    context_path = Path(context_path_str)
    if not context_path.exists():
        return {"status": "error", "error": f"context_path not found: {context_path}"}

    import json as _json

    context_doc = _json.loads(context_path.read_text(encoding="utf-8"))

    try:
        graph_settings = GraphSettings.from_env()
        embedder = BedrockEmbedder(
            region_name=graph_settings.aws_region,
            model_id=graph_settings.bedrock_embedding_model_id,
        )
        store = Neo4jGraphStore(graph_settings)
        store.ensure_schema(embedding_dimensions=embedder.embedding_dimensions)
        counts = store.ingest_agent_context(context_doc, embedder)
        store.close()
        return {"status": "ok", "ingested_counts": counts}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# State 4: RunDiagnosis
# ---------------------------------------------------------------------------

def run_diagnosis(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Execute the full agentic diagnostic orchestrator.

    Reads:
      event.question               — the diagnostic question.
      event.context.context_result — used as optional extra context.
    """
    from silo_smasher.orchestrator import (
        DiagnosticOrchestrator,
        OrchestratorSettings,
    )

    question = str(event.get("question", "Why did the metric change?")).strip()
    ctx_result = (event.get("context") or {}).get("context_result") or {}
    extra_context: str | None = None
    if ctx_result:
        import json as _json
        extra_context = _json.dumps(ctx_result, ensure_ascii=True)

    try:
        settings = OrchestratorSettings.from_env()
        orchestrator = DiagnosticOrchestrator(settings)
        result = orchestrator.run(question=question, extra_context=extra_context)
        result["run_id"] = str(uuid.uuid4())
        return result
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "question": question,
            "run_id": str(uuid.uuid4()),
        }


# ---------------------------------------------------------------------------
# State 5: LogMemoryToS3
# ---------------------------------------------------------------------------

def log_memory(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Persist the full pipeline result to S3 as an agent memory log.

    Reads:
      event.diagnosis.diagnosis   — the orchestrator output.
      event.question              — the original diagnostic question.
    """
    from silo_smasher.memory import MemoryLogger

    diagnosis_wrapper = event.get("diagnosis") or {}
    diagnosis = diagnosis_wrapper.get("diagnosis") or {}
    question = str(event.get("question", ""))
    run_id = str(diagnosis.get("run_id") or uuid.uuid4())

    logger = MemoryLogger.from_env()
    if not logger.is_active:
        return {
            "status": "skipped",
            "reason": "AWS_S3_MEMORY_BUCKET not configured.",
            "run_id": run_id,
        }

    s3_key = logger.log_run(run_id=run_id, question=question, result=diagnosis)
    return {
        "status": "ok" if s3_key else "error",
        "run_id": run_id,
        "s3_key": s3_key,
    }
