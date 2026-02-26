# Recommended Next Steps

All four phases from the original roadmap are complete: data ingestion, context normalization, graph RAG, orchestrator, all sponsor tool integrations, FastAPI, Render deployment, AWS Step Functions pipeline, and the demo frontend. What follows are the highest-leverage things to build next, ordered by impact.

---

## 1. The Scripted Demo Story

The synthetic data in `examples/synthetic_raw_bundle.json` is generic (random purchases). The winning demo storyboard is specific:

> "80% of the MRR drop is from customers using a specific UK shipping partner. A UK postal strike started this morning."

Currently the orchestrator will not naturally arrive at this conclusion because the data does not encode it. You need:

1. **A tailored synthetic bundle** — craft a `examples/uk_shipping_incident.json` where the purchase data clearly shows a regional drop in UK `Shipped` items starting at a specific timestamp, tied to a specific `shipping_partner_id`.
2. **A demo question** — `"MRR is down 15% this week. Why?"` — that, with the right data, will lead the agent through: graph traversal → regional revenue breakdown → Numeric variance → Tavily UK news → final verdict naming the shipping strike.
3. **A `demo/` run script** — a single `python demo/run_demo.py` that loads the tailored bundle, runs the full pipeline, and prints a formatted brief. This is your hackathon live demo fallback if the API is slow.

---

## 2. Activate Real Sponsor API Keys

Four sponsor integrations are currently in fallback mode because the keys are `__MISSING__`:

| Integration | What It Unlocks |
|---|---|
| **Senso** `SENSO_API_KEY` | Published context is verified against an external ground-truth store; the agent can cite Senso content IDs as provenance |
| **Yutori** `YUTORI_API_KEY` | Real browser automation — the agent can actually fetch internal portal PDFs, not just return a placeholder |
| **Numeric** `NUMERIC_API_KEY` | Real CFO-grade seasonal vs anomaly classification instead of the local heuristic |
| **Modulate** `MODULATE_API_KEY` | Real stress/intent detection from voice, not keyword regex |

For the hackathon, Numeric and Senso are the most demo-worthy because their outputs appear directly in the final executive brief.

---

## 3. Add a SQL / Structured Query Tool

The problem statement's core loop is: *generate hypotheses → write SQL to test each one*. Currently the orchestrator can query Neo4j (graph) and local context (manifest), but it cannot write and execute ad-hoc SQL.

**What to add:**
- A `run_sql_query` tool in `orchestrator/tools.py` that executes a parameterized read-only SQL query against a SQLite or Postgres database.
- Populate a local SQLite with the same `users / products / purchases` data from the context bundle.
- The orchestrator system prompt already instructs hypothesis testing — giving it SQL access closes the "Chat-to-Query" → "Autonomous Hypothesis Testing" gap that the problem statement identifies as the winning angle.

---

## 4. Add an Internal Unstructured Signal (Slack / Jira)

The problem statement's differentiating "third silo" beyond SQL and external news is:

> "The agent crawls Slack and finds: Dev team reported a bug in the UK checkout flow at 2 PM."

This is the piece that makes the demo feel genuinely cross-silo rather than just "SQL + search engine." Options from easiest to hardest:

- **Easiest:** A static `data/internal_signals/slack_messages.json` file with synthetic Slack messages. Add a `search_internal_communications` tool that keyword-searches it. No API key needed.
- **Medium:** Connect to a real Slack workspace via the Slack API (read-only `channels:history` scope). The orchestrator calls this when it suspects an internal bug or deployment.
- **Harder:** Jira/Linear integration to pull recent bug reports and incidents correlated by timestamp with the metric drop.

Even the fake-JSON version is sufficient for a demo and makes the story complete: SQL → graph → internal Slack → external news → confidence-scored verdict.

---

## 5. Proactive Metric Monitoring (Trigger Instead of Pull)

Currently Silo Smasher is reactive: a human asks a question. The vision in the problem statement is:

> "Detection: Agent monitors a live data stream. If sales drop, it generates theories automatically."

**What to add:**
- A `/monitor` endpoint that accepts a metric name, threshold, and check interval.
- A background task (FastAPI `BackgroundTasks` or a simple cron Lambda) that periodically queries the data, computes the metric, and fires `POST /diagnose` automatically when it drops past the threshold.
- Store the auto-triggered result in S3 memory and optionally send a notification (Slack webhook, email via SES).

This transforms the tool from a "consultant you call" into an "analyst who calls you."

---

## 6. Test Suite

There are currently no tests. Adding a minimal set would catch regressions and make the codebase shareable:

- `tests/test_normalize.py` — unit test `normalize_raw_bundle()` against `examples/synthetic_raw_bundle.json`. Assert field presence, metric math (conversion rate, return rate), and schema version.
- `tests/test_orchestrator_fallback.py` — with no API keys set, assert that `DiagnosticOrchestrator.run("test question")` returns a dict containing `"error": "all_providers_failed"` and a populated `"fallback_response"` rather than raising.
- `tests/test_health.py` — spin up a `TestClient` and assert `/health` returns `{"status": "ok"}` regardless of S3/Step Functions configuration.

Run with: `pytest tests/`

---

## 7. MCP Server Exposure

The problem statement specifically mentions Model Context Protocol as a winning technique:

> "Use MCP servers to connect your agent directly to local SQLite, Postgres, or even Google Sheets."

Exposing the Neo4j GraphRAG and the Senso system-of-record as MCP tool servers would allow any MCP-compatible host (Claude Desktop, Cursor, etc.) to use Silo Smasher as a data intelligence backend — significantly expanding the addressable audience beyond the REST API.

**What to add:**
- An `mcp/` directory with a Python MCP server that exposes `query_graph_connections` and `get_senso_content` as MCP tools.
- Add `mcp` to dependencies (`pip install mcp`).
- The server can be started locally with `python mcp/server.py` and connected from Claude Desktop.
