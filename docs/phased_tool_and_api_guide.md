# Phased Tool and API Guide

This document explains how and why each integrated tool is used, phase by phase, and maps the exact API surfaces used in code.

## Phase 1: Synthetic Source Pull with Airbyte

### Why this phase exists
- Establish repeatable source data ingestion using Airbyte so the rest of the pipeline receives consistent records.
- Keep source bootstrap logic scriptable for demos and quick resets.

### Tool used
- Airbyte Public API (through `airbyte-api` SDK).

### How it is used
- Script entry: `python -m airbyte_synthetic_data_pipeline.synthetic_sync`.
- The script authenticates via either bearer token or basic auth.
- It finds workspace/source/connection resources and creates missing ones.
- It can trigger and poll sync jobs when requested.

### API operations used
- `workspaces.list_workspaces`
- `sources.list_sources`
- `sources.create_source`
- `destinations.list_destinations`
- `streams.get_stream_properties`
- `connections.list_connections`
- `connections.create_connection`
- `jobs.create_job`
- `jobs.get_job`

### Code references
- `src/airbyte_synthetic_data_pipeline/synthetic_sync.py`

### Key inputs and outputs
- Inputs: `AIRBYTE_SERVER_URL`, auth env vars, source/destination/workspace ids.
- Output: reusable source + connection, optional completed sync job metadata.

## Phase 2: Raw-to-Agent Context Normalization (System of Record)

### Why this phase exists
- Convert raw records into deterministic, schema-stable `agent_ready_context` JSON.
- Produce auditable artifacts that can be re-used by graph ingestion and orchestration.

### Tool used
- Local normalization pipeline (no external API call in this phase).

### How it is used
- Command: `build-agent-context --input <raw.json> --source-name <name>`.
- Accepts bundle format or Airbyte RECORD message format.
- Persists:
  - raw snapshot
  - normalized context
  - manifest entry

### Code references
- `src/airbyte_synthetic_data_pipeline/context/normalize.py`
- `src/airbyte_synthetic_data_pipeline/pipeline/ground_truth.py`
- `src/airbyte_synthetic_data_pipeline/cli/build_agent_context.py`

### Key inputs and outputs
- Input: raw bundle or Airbyte message JSON.
- Output: files under `data/system_of_record/{raw_snapshots,agent_context,manifest.jsonl}`.

## Phase 3: Verified Ground Truth with Senso

### Why this phase exists
- Store normalized context in an external System of Record.
- Verify that stored text matches local output via hash comparison.
- Enable "ground truth" fallback when agent output is questioned.

### Tool used
- Senso API.

### How it is used
- Optional mode in `build-agent-context` via `--publish-to-senso`.
- Publishes both raw snapshot and normalized context.
- Polls processing status until complete.
- Computes SHA256 for local and returned context text and asserts equality.

### API endpoints used
- `POST /content/raw`
- `GET /content/{content_id}`

### Code references
- `src/airbyte_synthetic_data_pipeline/senso/client.py`
- `src/airbyte_synthetic_data_pipeline/senso/publish.py`
- `src/airbyte_synthetic_data_pipeline/pipeline/ground_truth.py`

### Key inputs and outputs
- Input: `SENSO_API_KEY` and optional Senso timing/base URL vars.
- Output: Senso content ids and verification receipt JSON.

## Phase 4: Entity Relationship Graph and GraphRAG

### Why this phase exists
- Represent business entity relationships explicitly (`Customer -> Order -> SupportTicket -> Product`).
- Support "why connected" retrieval, not only nearest-neighbor vector recall.

### Tools used
- Neo4j AuraDB (graph store + vector index).
- AWS Bedrock embeddings (`InvokeModel`) for retrieval vectors.

### How it is used
- Command: `sync-graph-context` ingests latest local context.
- Creates constraints and vector index.
- Upserts nodes and relationships.
- Command: `query-graph-rag` runs vector seeding + graph expansion.

### API surfaces used
- Neo4j driver operations and Cypher:
  - schema creation
  - vector index query (`db.index.vector.queryNodes`)
  - multi-hop path expansion
  - relationship link query for `Customer/Order/SupportTicket`
- AWS Bedrock runtime:
  - `InvokeModel` for text embeddings

### Code references
- `src/airbyte_synthetic_data_pipeline/graph/config.py`
- `src/airbyte_synthetic_data_pipeline/graph/store.py`
- `src/airbyte_synthetic_data_pipeline/graph/bedrock_embedder.py`
- `src/airbyte_synthetic_data_pipeline/graph/graphrag.py`
- `src/airbyte_synthetic_data_pipeline/cli/sync_graph_context.py`
- `src/airbyte_synthetic_data_pipeline/cli/query_graph_rag.py`

### Key inputs and outputs
- Inputs: `NEO4J_*`, `AWS_*`, optional `BEDROCK_EMBEDDING_MODEL_ID`.
- Output: ingested graph, vector index, explainable path evidence for queries.

## Phase 5: Orchestrator Runtime (Primary + Backup Model Routing)

### Why this phase exists
- Turn data access into an agent workflow that can test hypotheses using tools.
- Provide resilient model routing with primary and fallback providers.

### Tools used
- OpenAI Responses API (primary).
- Gemini SDK/API (backup provider).

### How it is used
- Command: `run-diagnostic-orchestrator --question "..."`.
- Runtime builds a tool catalog and enters iterative tool-calling loops.
- Provider order is configured by env vars.
- If primary fails, fallback is attempted.

### API surfaces used
- OpenAI:
  - `client.responses.create(...)` with tool schemas and tool outputs
- Gemini:
  - `client.models.generate_content(...)` with function declarations and tool responses

### Code references
- `src/airbyte_synthetic_data_pipeline/orchestrator/config.py`
- `src/airbyte_synthetic_data_pipeline/orchestrator/agent.py`
- `src/airbyte_synthetic_data_pipeline/orchestrator/tools.py`
- `src/airbyte_synthetic_data_pipeline/cli/run_diagnostic_orchestrator.py`

### Key inputs and outputs
- Inputs: `OPENAI_API_KEY`, `GEMINI_API_KEY`, model routing vars.
- Output: structured diagnostic JSON with hypotheses, evidence, confidence.

## Phase 6: Fastino Privacy and Action Guardrails

### Why this phase exists
- Prevent sensitive values from reaching model providers.
- Block risky tool actions before execution.

### Tool used
- Fastino API (plus local fallback patterns if service is unavailable).

### How it is used
- Before sending prompt to model: run PII redaction.
- Before every tool execution: run action-risk classification.
- Result is attached in `_safety` metadata in orchestrator output.

### API endpoint used
- `POST /gliner-2`
  - task `extract_entities` for redaction
  - task `classify_text` for action blocking

### Code references
- `src/airbyte_synthetic_data_pipeline/guardrails/fastino.py`
- `src/airbyte_synthetic_data_pipeline/orchestrator/agent.py`

### Key inputs and outputs
- Input: `FASTINO_API_KEY` and guardrail config vars.
- Output: sanitized prompt, allowed/blocked tool-call decisions, safety report.

## Phase 7: Yutori Web Navigation Fallback

### Why this phase exists
- Retrieve latest portal reports when structured DB context is incomplete.
- Handle internal dashboard/report workflows where no API is available.

### Tool used
- Yutori Browsing API.

### How it is used
- Exposed as orchestrator tool: `fetch_portal_report_with_web_navigation`.
- Creates a browsing task against internal portal URL.
- Polls task status until completion/failure/timeout.
- Returns result payload for grounded evidence extraction.
- If `YUTORI_API_KEY` is missing, returns a local system-of-record fallback summary instead of failing.

### API endpoints used
- `POST /v1/browsing/tasks`
- `GET /v1/browsing/tasks/{task_id}`

### Code references
- `src/airbyte_synthetic_data_pipeline/web_navigation/navigator_client.py`
- `src/airbyte_synthetic_data_pipeline/orchestrator/tools.py`
- `src/airbyte_synthetic_data_pipeline/orchestrator/agent.py`

### Key inputs and outputs
- Input: `YUTORI_API_KEY` and Yutori runtime vars.
- Output: task result payload with report retrieval state and extracted content.

## Phase 8: Numeric Variance Analysis (Finance Brain)

### Why this phase exists
- Add CFO-level interpretation for revenue movement, not just raw metric change.
- Classify declines as seasonal variance vs likely accounting anomaly.

### Tool used
- Numeric Variance API (with local fallback heuristic).

### How it is used
- Exposed as orchestrator tool: `analyze_revenue_variance`.
- Sends current/prior revenue and optional context (`period`, `region`, baseline trend).
- Returns classification, confidence, and explanation text.
- If `NUMERIC_API_KEY` is missing or API fails, local materiality-based fallback still returns an explanation.

### API endpoint used
- Configurable POST endpoint (default path):
  - `POST /v1/variance/analysis`

### Code references
- `src/airbyte_synthetic_data_pipeline/finance/variance_client.py`
- `src/airbyte_synthetic_data_pipeline/orchestrator/tools.py`
- `src/airbyte_synthetic_data_pipeline/orchestrator/agent.py`

### Key inputs and outputs
- Input: `NUMERIC_API_KEY` and Numeric runtime vars.
- Output: `seasonal/anomaly` classification with CFO-style explanation.

## Phase 9: Tavily External-World Signals

### Why this phase exists
- Validate internal variance findings against real-world events.
- Add external economic context for regional revenue declines.

### Tool used
- Tavily Search API.

### How it is used
- Exposed as orchestrator tool: `search_external_economic_news`.
- Typical usage after finance variance flags regional decline.
- Example query pattern: \"Major economic news in Japan in the last 24 hours\".
- If `TAVILY_API_KEY` is missing or request fails, returns a fallback with suggested manual queries.

### API endpoint used
- `POST /search`

### Code references
- `src/airbyte_synthetic_data_pipeline/market_signals/tavily_client.py`
- `src/airbyte_synthetic_data_pipeline/orchestrator/tools.py`
- `src/airbyte_synthetic_data_pipeline/orchestrator/agent.py`

### Key inputs and outputs
- Input: `TAVILY_API_KEY` and Tavily runtime vars.
- Output: answer summary plus article links/snippets for external signals.

## Phase 10: End-to-End Runtime Sequence

1. Pull or reuse source data through Airbyte.
2. Normalize into deterministic agent-ready context.
3. Optionally publish to Senso and verify hash parity.
4. Ingest context into Neo4j and embed with Bedrock.
5. Run orchestrator to test hypotheses with tool calls.
6. Apply Fastino guardrails before provider calls and tool execution.
7. If DB evidence is missing, fetch latest internal portal report through Yutori (or local fallback).
8. If revenue dips, run Numeric variance analysis for CFO-level classification.
9. If a regional external cause is plausible, run Tavily search for recent economic events.

## Tool-to-Phase Matrix

| Tool | Phase(s) | Primary reason |
|---|---|---|
| Airbyte Public API | 1 | Deterministic synthetic-source ingestion and sync orchestration |
| Local Normalizer | 2 | Canonical context generation and reproducible artifacts |
| Senso API | 3 | External verified ground truth and provenance |
| Neo4j AuraDB | 4 | Relationship-aware retrieval and explainability |
| AWS Bedrock | 4 | Embedding generation for vector seeding |
| OpenAI Responses | 5 | Primary tool-using diagnostic orchestration |
| Gemini API | 5 | Backup orchestration provider for resiliency |
| Fastino API | 6 | PII redaction and risky-action blocking |
| Yutori Browsing API | 7 | Web-portal evidence capture when APIs are unavailable |
| Numeric Variance API | 8 | Finance-grade seasonal vs anomaly classification for revenue dips |
| Tavily Search API | 9 | Outside-world economic signal detection for root-cause support |

## Notes on Defaults vs Unique Secrets

- Unique secrets are intentionally never auto-generated in code.
- Non-secret defaults are set in `.env.example` and can be prefilled in local `.env`.
- Required unique keys depend on the flow you execute.
