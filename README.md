# Silo Smasher

**Autonomous Root-Cause Investigator** — Graph-Augmented Agentic BI.

Current tools show *what* changed. Silo Smasher explains *why*.

When a metric drops, the agent generates hypotheses and autonomously tests them by correlating three types of evidence that no existing BI tool combines:

1. **Structured data** (SQL / Airbyte syncs) — "Sales dropped 20% in the UK."
2. **Internal graph context** (Neo4j — Customer → Order → SupportTicket chains) — "80% of the drop is from a specific shipping partner."
3. **External signals** (Tavily news search) — "UK postal strike started this morning."

Final output: a confidence-scored executive brief with the most likely root cause and recommended next steps.

---

## Architecture — The Silo Smasher Stack

```
Airbyte ──► Context Normaliser ──► Senso (System of Record)
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
            (Finance Variance)   (External News)    (Voice Interface)
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
│   ├── orchestrator/           # OpenAI (primary) + Gemini (fallback) agent loop
│   ├── pipeline/               # Ground-truth pipeline (Airbyte → context → Senso)
│   ├── senso/                  # Senso system-of-record client
│   ├── structured_query/       # SQLite read-only SQL tool for hypothesis testing
│   ├── voice_interface/        # Modulate voice command analyser
│   ├── web_navigation/         # Yutori browser automation client
│   └── cli/                   # CLI entry points
├── data/system_of_record/      # Local artefacts (raw snapshots, context JSON, manifest)
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

### 3. Run a diagnostic investigation

```bash
run-diagnostic-orchestrator \
  --question "Sales are down 12% week-over-week. Why?"
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
  -d '{"question": "Why did MRR drop 15%?"}'
```

---

## REST API

| Endpoint | Description |
|---|---|
| `GET /health` | Liveness + S3/Step Functions status |
| `POST /diagnose` | Synchronous root-cause investigation |
| `GET /memory` | List past diagnostic runs from S3 |
| `GET /memory/{key}` | Fetch a specific memory log |
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
| **Neo4j** | Knowledge graph — Customer→Order→SupportTicket traversal | `graph/` |
| **OpenAI** | Primary orchestrator (GPT-4o) | `orchestrator/agent.py` |
| **Gemini** | Fallback orchestrator | `orchestrator/agent.py` |
| **Fastino** | Guardrails — PII redaction + action safety | `guardrails/` |
| **Yutori** | Web navigation — internal portal PDF extraction | `web_navigation/` |
| **Numeric** | Finance variance — seasonal vs anomaly classification | `finance/` |
| **Tavily** | External news search — real-world economic signals | `market_signals/` |
| **Modulate** | Voice interface — intent/emotion → summary vs deep-dive | `voice_interface/` |
| **Senso** | System-of-record — verified ground-truth context | `senso/` |
| **AWS** | Bedrock embeddings + S3 memory + Step Functions pipeline | `graph/`, `memory/`, `aws/` |
| **Render** | API hosting | `Dockerfile`, `render.yaml` |
