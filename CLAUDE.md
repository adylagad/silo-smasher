# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Silo Smasher** is an Autonomous Root-Cause Investigator. When a business metric drops, it generates hypotheses and autonomously tests them by correlating structured data (SQL/Airbyte), internal graph context (Neo4j — Customer→Order→SupportTicket chains), and external signals (Tavily news search). Output is a confidence-scored executive brief.

## Development Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
cp .env.example .env  # fill in API keys
```

## CLI Commands

```bash
# 1. Normalize raw data bundle into agent-ready context
build-agent-context --input examples/synthetic_raw_bundle.json

# 2. Push normalized context into Neo4j (requires NEO4J_* + AWS_* env vars)
sync-graph-context

# 3. Run a diagnostic investigation (requires OPENAI_API_KEY)
run-diagnostic-orchestrator --question "Sales are down 12% WoW. Why?"

# 4. Query Neo4j GraphRAG directly
query-graph-rag --question "Which customers had shipping issues?" --top-k 5 --max-hops 2

# 5. Start the REST API locally
uvicorn api.main:app --reload  # → http://localhost:8000/docs

# 6. Deploy AWS infrastructure (S3 + Lambda + Step Functions)
python aws/deploy.py
```

There are no tests and no linter configured.

## Architecture

### Data Flow

```
examples/synthetic_raw_bundle.json
  → context/normalize.py          # raw bundle → agent_context JSON
  → data/system_of_record/        # persisted locally (manifest.jsonl)
  → senso/                        # optional: publish to Senso system-of-record
  → graph/ (Neo4j + Bedrock)      # optional: embed + ingest into Neo4j
  → orchestrator/ (OpenAI/Gemini) # agentic tool-call loop → root-cause brief
```

### Core Package: `src/silo_smasher/`

**`context/`** — `normalize_raw_bundle()` converts `{users, products, purchases}` JSON into a structured `agent_context` document with computed metrics (conversion_rate, return_rate, gross/net revenue, country breakdown). This is the canonical internal data format.

**`orchestrator/`** — `DiagnosticOrchestrator.run(question)` drives the agentic loop. Provider order: OpenAI (primary) → Gemini (fallback) → local JSON fallback. The loop runs up to 8 tool-call rounds. All tool results flow through `FastinoSafetyEngine` before and after execution. The OpenAI client is lazily initialized (only created when `OPENAI_API_KEY` is present) so the app starts cleanly even without keys.

**`orchestrator/tools.py`** — `DiagnosticToolRuntime` registers 7 tools:
| Tool | Module | Purpose |
|---|---|---|
| `query_graph_connections` | `graph/` | Neo4j vector + graph traversal |
| `get_senso_content` | `senso/` | Fetch verified ground-truth |
| `get_latest_system_record_entries` | local manifest | Always-available fallback |
| `fetch_portal_report_with_web_navigation` | `web_navigation/` | Yutori browser automation |
| `analyze_revenue_variance` | `finance/` | Numeric.io seasonal vs anomaly |
| `search_external_economic_news` | `market_signals/` | Tavily news search |
| `analyze_voice_command_mode` | `voice_interface/` | Modulate stress/intent detection |

**`graph/`** — `GraphRAGService` embeds the query via AWS Bedrock (Titan Embeddings V2), finds top-k similar nodes in Neo4j via cosine vector search, then expands 1–3 hops along relationships (Customer→Order→SupportTicket→Product). Schema nodes: `Customer`, `Product`, `Order`, `SupportTicket` (all carry `:Retrievable` label + `.embedding` property).

**`guardrails/`** — `FastinoSafetyEngine` wraps Fastino's API for PII redaction and action safety classification. Local regex fallback always active. Default `fail_mode: open` means guardrail service outages don't block requests. Blocked action categories: `dangerous_financial_action`, `credential_exposure`, `data_exfiltration`, `destructive_data_change`.

**`pipeline/`** — `run_ground_truth_pipeline()` is the single function used by both the CLI (`build-agent-context`) and the Lambda `BuildAgentContext` handler. Outputs to `data/system_of_record/` with timestamped files + appends to `manifest.jsonl`.

**`memory/`** — `MemoryLogger` writes diagnostic run results to S3 as `diagnostic-runs/YYYY/MM/DD/<run_id>.json`. Silently no-ops when `AWS_S3_MEMORY_BUCKET` is not set.

### REST API: `api/`

`api/main.py` exposes 6 endpoints via FastAPI. The `DiagnosticOrchestrator` and `MemoryLogger` are instantiated once in the `lifespan` context manager. `/diagnose` is synchronous (runs the full agentic loop inline). `/pipeline` starts an AWS Step Functions execution and returns an `execution_arn` to poll with `GET /pipeline/{arn}`.

### AWS Async Pipeline: `aws/`

`aws/deploy.py` is a one-shot deployment script that creates S3, IAM roles, 5 Lambda functions, and the `DiagnosticPipeline` Step Functions state machine, writing ARNs back into `.env`.

`aws/handlers/pipeline_handlers.py` contains the 5 Lambda handler functions (one per Step Functions state): `ingest_data` → `build_agent_context` → `sync_graph_context` → `run_diagnosis` → `log_memory`. Note: the directory is named `handlers/` (not `lambda/`) because `lambda` is a Python reserved word.

The state machine at `aws/step_functions/state_machine.json` has Retry + Catch on every state so the pipeline continues even when Airbyte or Neo4j are unconfigured.

### Fallback Convention

Every external API client follows the same pattern:
1. Check for API key; return a structured error dict if missing (never raise at startup).
2. On HTTP failure: if `fallback_enabled=True` (default), return a locally-computed result.
3. All tool call failures in `tools.py` fall back to `get_latest_system_record_entries` (local manifest).

Placeholder API keys in `.env` use the sentinel `__MISSING__` — all `_clean_api_key()` helpers treat this as `None`.

## Key Environment Variables

| Variable | Used By | Notes |
|---|---|---|
| `OPENAI_API_KEY` | Orchestrator (primary) | Required for real diagnoses |
| `GEMINI_API_KEY` | Orchestrator (fallback) | Optional |
| `NEO4J_URI` / `NEO4J_USERNAME` / `NEO4J_PASSWORD` | `graph/` | Neo4j AuraDB |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` | Bedrock, S3, Step Functions | |
| `AWS_S3_MEMORY_BUCKET` | `memory/` | Set by `aws/deploy.py` |
| `AWS_STEP_FUNCTIONS_STATE_MACHINE_ARN` | `api/main.py` `/pipeline` | Set by `aws/deploy.py` |
| `FASTINO_API_KEY` | `guardrails/` | Falls back to local regex if missing |
| `TAVILY_API_KEY` | `market_signals/` | Falls back to empty results |

## Deployed Services

- **Render API:** `https://silo-smasher.onrender.com` (Docker, free tier, `$PORT` injected at runtime)
- **GitHub repo:** `https://github.com/adylagad/silo-smasher`
- **Step Functions:** `arn:aws:states:us-east-1:782998891728:stateMachine:DiagnosticPipeline`
- **S3 memory bucket:** `airbyte-diagnostic-memory-782998891728`
