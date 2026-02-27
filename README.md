# Silo Smasher

**Autonomous Incident Engineer** — Graph-Augmented Incident Response.

Traditional monitoring tells you *that* something broke. Silo Smasher explains *why* and what to do next.

When a service starts returning HTTP 500, the agent generates hypotheses and tests them by correlating evidence across systems:

1. **Structured data** (SQL / telemetry) — "500/min jumped 20x after deploy."
2. **Internal incident context** (logs, deploy metadata, traces, comms) — "Commit `9f3c1b7` introduced a null dereference."
3. **External signals** (cloud/provider status) — "No regional outage, so likely app regression."

Final output: a confidence-scored incident brief with root cause, mitigation actions, and PR draft direction.

---

## Architecture — The Incident Stack

```
Airbyte / Incident Snapshot ──► Context Normaliser ──► Senso (System of Record)
                                        │
                              Neo4j AuraDB GraphRAG
                              (AWS Bedrock embeddings)
                                        │
                    ┌───────────────────┼────────────────────┐
                    │                   │                    │
              Fastino               OpenAI / Gemini       Yutori
            (Guardrails)            Orchestrator       (Web Navigation)
                    │                   │                    │
                Numeric              Tavily             Modulate
             (Risk Lens)       (Cloud/World Status) (Voice Interface)
                                        │
                              FastAPI REST API
                                        │
                    ┌───────────────────┼────────────────────┐
                    │                                        │
              Render (API host)                   AWS Step Functions
                                             (5-step async pipeline)
                                                  S3 Memory Logs
```

---

## Project Layout

```
silo-smasher/
├── api/                        # FastAPI backend
│   ├── main.py                 # /health /diagnose /memory /pipeline
│   └── models.py
├── aws/
│   ├── deploy.py               # One-shot AWS deployment script
│   ├── handlers/
│   │   └── pipeline_handlers.py  # Lambda handlers (5 states)
│   └── step_functions/
│       └── state_machine.json  # Step Functions state machine definition
├── src/silo_smasher/           # Core Python package
│   ├── context/                # Raw-bundle → agent-ready context normaliser
│   ├── finance/                # Numeric variance analysis client
│   ├── graph/                  # Neo4j GraphRAG + AWS Bedrock embedder
│   ├── guardrails/             # Fastino PII redaction + action safety
│   ├── market_signals/         # Tavily external economic news
│   ├── memory/                 # S3 memory log writer/reader
│   ├── monitoring/             # Proactive metric monitors + auto-trigger runtime
│   ├── orchestrator/           # OpenAI (primary) + Gemini (fallback) agent loop
│   ├── pipeline/               # Ground-truth pipeline (Airbyte → context → Senso)
│   ├── senso/                  # Senso system-of-record client
│   ├── structured_query/       # SQLite read-only SQL tool for hypothesis testing
│   ├── voice_interface/        # Modulate voice command analyser
│   ├── web_navigation/         # Yutori browser automation client
│   └── cli/                   # CLI entry points
├── mcp/                        # MCP server exposure (graph + Senso tools)
│   ├── server.py
│   └── README.md
├── data/system_of_record/      # Local artefacts (raw snapshots, context JSON, manifest)
├── data/internal_signals/       # Synthetic Slack/Jira-style internal messages
├── examples/
│   └── synthetic_raw_bundle.json
├── Dockerfile
├── render.yaml
└── .env.example
```

---

## Quick Start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
cp .env.example .env   # fill in API keys
```

### Mock Mode For Unavailable APIs

If sponsor APIs are temporarily unavailable, keep the demo flowing with deterministic mock payloads:

```bash
SPONSOR_MOCK_DATA_ENABLED=true
ORCHESTRATOR_ENABLE_LOCAL_DEMO_FALLBACK=true
```

This preserves existing local fallbacks and adds richer mock outputs for Numeric, Tavily, Yutori, Modulate, and Senso tool calls.
Set it to `false` after all live API keys are stable.

### 1. Build local context (no Airbyte needed)

```bash
build-agent-context --input examples/synthetic_raw_bundle.json
```

### 2. Load into Neo4j graph

```bash
sync-graph-context
```

### 2b. Validate structured SQL data (optional)

`build-agent-context` now mirrors the same bundle into SQLite at
`data/system_of_record/sqlite/commerce.db` for the orchestrator `run_sql_query` tool.

```bash
sqlite3 data/system_of_record/sqlite/commerce.db \
  "SELECT status, COUNT(*) AS count FROM purchases GROUP BY status ORDER BY count DESC;"
```

### 2c. Validate internal unstructured signals (optional)

The easiest internal-signal path is already wired with synthetic messages in:
`data/internal_signals/incident_war_room_messages.json`

The orchestrator can search this through `search_internal_communications` with no API key.

### 3. Run an incident investigation

```bash
run-diagnostic-orchestrator \
  --question "Checkout API started returning HTTP 500 after deploy. Find root cause and mitigation."
```

### 3b. Run deterministic incident demo

```bash
python demo/run_incident_demo.py
```

### 4. Start the REST API

```bash
uvicorn api.main:app --reload
# → http://localhost:8000/docs
```

### 5. Trigger the full async pipeline (Step Functions)

```bash
curl -X POST http://localhost:8000/pipeline \
  -H "Content-Type: application/json" \
  -d '{"question": "Why did checkout-api start returning HTTP 500 after deploy?"}'
```

### 6. Start proactive monitoring (trigger instead of pull)

```bash
curl -X POST http://localhost:8000/monitor \
  -H "Content-Type: application/json" \
  -d '{
    "metric_name": "net_revenue",
    "drop_threshold_pct": 15,
    "check_interval_seconds": 60,
    "comparison_window_hours": 24,
    "baseline_window_hours": 24
  }'
```

Then check monitor state:

```bash
curl http://localhost:8000/monitor
```

### 7. Run MCP server exposure

```bash
python mcp/server.py --transport stdio
```

Optional HTTP transport:

```bash
python mcp/server.py --transport streamable-http --host 127.0.0.1 --port 8001 --mount-path /mcp
```

---

## REST API

| Endpoint | Description |
|---|---|
| `GET /health` | Liveness + S3/Step Functions status |
| `POST /diagnose` | Synchronous root-cause investigation |
| `GET /memory` | List past diagnostic runs from S3 |
| `GET /memory/{key}` | Fetch a specific memory log |
| `POST /monitor` | Start proactive metric monitor |
| `GET /monitor` | List monitor states |
| `GET /monitor/{id}` | Fetch one monitor |
| `POST /monitor/{id}/check` | Force an immediate monitor check |
| `DELETE /monitor/{id}` | Stop a monitor |
| `POST /pipeline` | Start async Step Functions pipeline |
| `GET /pipeline/{arn}` | Poll pipeline execution status |

Interactive docs: `/docs`

---

## AWS Deployment

```bash
# Requires IAM permissions: S3, Lambda, IAM, Step Functions
python aws/deploy.py
```

Deploys:
- S3 bucket for memory logs
- 5 Lambda functions (one per pipeline stage)
- IAM execution roles
- Step Functions `DiagnosticPipeline` state machine

ARNs are written back to `.env` automatically.

## Render Deployment

Push to GitHub, connect repo in [render.com](https://render.com). `render.yaml` is auto-detected. Set secret env vars in the Render dashboard.

---

## Sponsor Integrations

| Sponsor | Role | Module |
|---|---|---|
| **Airbyte** | Data pipeline — pulls records from any source | `synthetic_sync.py` |
| **Neo4j** | Knowledge graph — Service→Deploy→Incident→Ticket traversal context | `graph/` |
| **OpenAI** | Primary orchestrator (GPT-4o) | `orchestrator/agent.py` |
| **Gemini** | Fallback orchestrator | `orchestrator/agent.py` |
| **Fastino** | Guardrails — PII redaction + action safety | `guardrails/` |
| **Yutori** | Web navigation — internal portal PDF extraction | `web_navigation/` |
| **Numeric** | Risk lens — anomaly framing when impact severity is unclear | `finance/` |
| **Tavily** | External status/news search — cloud/vendor context | `market_signals/` |
| **Modulate** | Voice interface — intent/emotion → summary vs deep-dive | `voice_interface/` |
| **Senso** | System-of-record — verified ground-truth context | `senso/` |
| **Internal Signals (Local)** | Synthetic incident war-room messages for engineering correlation | `internal_signals/`, `data/internal_signals/incident_war_room_messages.json` |
| **AWS** | Bedrock embeddings + S3 memory + Step Functions pipeline | `graph/`, `memory/`, `aws/` |
| **Render** | API hosting | `Dockerfile`, `render.yaml` |
