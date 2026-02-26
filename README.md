# Airbyte Synthetic Data Pipeline

Pipeline for three jobs:

1. Create/reuse a synthetic Airbyte source and run syncs.
2. Normalize raw records into deterministic `agent_ready_context` JSON (System of Record).
3. Load entities into Neo4j AuraDB and run GraphRAG with AWS Bedrock embeddings.
4. Run an OpenAI orchestrator agent with tool access to GraphRAG and Senso context.

Detailed phase-by-phase documentation:
- `docs/phased_tool_and_api_guide.md`

## Project Layout

```text
airbyte-synthetic-data-pipeline/
  data/system_of_record/
    raw_snapshots/
    agent_context/
    receipts/
    manifest.jsonl
  examples/
    synthetic_raw_bundle.json
  src/airbyte_synthetic_data_pipeline/
    context/
    senso/
    graph/
      config.py
      bedrock_embedder.py
      store.py
      graphrag.py
    guardrails/
      fastino.py
    finance/
      variance_client.py
    market_signals/
      tavily_client.py
    voice_interface/
      modulate_client.py
    web_navigation/
      navigator_client.py
    orchestrator/
      config.py
      tools.py
      agent.py
    pipeline/
      ground_truth.py
    cli/
      build_agent_context.py
      sync_graph_context.py
      query_graph_rag.py
      run_diagnostic_orchestrator.py
    synthetic_sync.py
```

## Setup

```bash
cd /Users/aditya/repos/hacks/airbyte-synthetic-data-pipeline
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m pip install -e .
cp .env.example .env
```

## Airbyte Bootstrap

```bash
cd /Users/aditya/repos/hacks/airbyte-synthetic-data-pipeline
source .venv/bin/activate
python -m airbyte_synthetic_data_pipeline.synthetic_sync --source-name catalog-source --count 500 --seed 123
```

## Build Agent-Ready Context (Local System of Record)

```bash
cd /Users/aditya/repos/hacks/airbyte-synthetic-data-pipeline
source .venv/bin/activate
build-agent-context --input examples/synthetic_raw_bundle.json --source-name airbyte_synthetic_source
```

Accepted input formats:

- Bundle JSON with keys `users`, `products`, `purchases`
- Airbyte message JSON (`RECORD` messages), either as top-level list or `{ "messages": [...] }`

## GraphRAG: Load to Neo4j AuraDB

```bash
cd /Users/aditya/repos/hacks/airbyte-synthetic-data-pipeline
source .venv/bin/activate
sync-graph-context
```

This command:

- picks the latest context file from `data/system_of_record/agent_context/` (or use `--context-file`)
- creates graph schema and vector index (if missing)
- upserts `Customer`, `Order`, `SupportTicket`, `Product` nodes
- creates relationship chains:
  - `(:Customer)-[:PLACED]->(:Order)-[:CONTAINS_PRODUCT]->(:Product)`
  - `(:Customer)-[:OPENED_TICKET]->(:SupportTicket)-[:ABOUT_ORDER]->(:Order)`
- generates embeddings via AWS Bedrock and stores them on `:Retrievable` nodes
- auto-falls back from `neo4j+s://` to `neo4j+ssc://` if Aura routing handshake fails in your local runtime

## GraphRAG: Query Why Data Is Connected

```bash
cd /Users/aditya/repos/hacks/airbyte-synthetic-data-pipeline
source .venv/bin/activate
query-graph-rag --question "Which customers had returns and which orders are linked?" --top-k 5 --max-hops 2
```

Output includes:

- vector-relevant seed nodes
- graph-expanded path evidence
- explicit `Customer -> Order -> SupportTicket` link rows
- human-readable edge reasons explaining connections

## Neo4j AuraDB + AWS Setup (Step by Step)

1. Create a Neo4j AuraDB instance (Free or Professional).
2. In Aura, copy:
   - connection URI (looks like `neo4j+s://<id>.databases.neo4j.io`)
   - username (`neo4j`)
   - password
3. In AWS, use an IAM user/role with `bedrock:InvokeModel`.
4. In AWS Bedrock console, enable model access for `Amazon Titan Text Embeddings V2`.
5. Put these in `.env`:
   - `NEO4J_URI`
   - `NEO4J_USERNAME`
   - `NEO4J_PASSWORD`
   - `AWS_REGION` (Bedrock-enabled region)
   - optional: `BEDROCK_EMBEDDING_MODEL_ID` (default `amazon.titan-embed-text-v2:0`)
6. Make sure AWS credentials are available locally (`aws configure`, SSO, or environment variables).
7. Run `sync-graph-context`.
8. Run `query-graph-rag` and confirm you see `why_connected_paths` and `customer_order_ticket_links`.

## Orchestrator (OpenAI Primary, Gemini Backup)

```bash
cd /Users/aditya/repos/hacks/airbyte-synthetic-data-pipeline
source .venv/bin/activate
run-diagnostic-orchestrator \
  --question "Sales are down 12% week-over-week. Generate hypotheses and test with tools."
```

Default behavior:

- OpenAI is the primary provider
- Gemini is an automatic backup if OpenAI fails (for example quota/rate limits)
- Fastino guardrails redact sensitive values before provider calls
- Fastino guardrails check each tool action and block high-risk operations
- Yutori web navigation fetches latest internal portal PDF evidence when DB context is missing
- Yutori gracefully falls back to local system-of-record summary when web credentials are unavailable
- Numeric variance analysis classifies revenue dips as seasonal vs anomaly with CFO-style explanation
- Tavily external search adds real-world economic context (for example major Japan news in last 24 hours)
- Modulate voice mode detects intent/emotion and prioritizes summary mode if the speaker sounds stressed

The orchestrator uses function tools:

- `query_graph_connections`: runs GraphRAG on Neo4j + Bedrock
- `get_senso_content`: fetches verified context by Senso content id
- `get_latest_system_record_entries`: reads local manifest/context previews for grounding
- `fetch_portal_report_with_web_navigation`: logs into internal portal and extracts latest PDF report evidence
- `analyze_revenue_variance`: asks finance variance analysis if revenue dip is seasonal or anomalous
- `search_external_economic_news`: checks outside-world economic news for a specific country/region
- `analyze_voice_command_mode`: detects voice intent/emotion and recommends summary vs deep-dive mode

Expected final output is structured JSON with:

- metric summary
- tested hypotheses
- confidence scores
- likely root cause
- suggested next queries

## Orchestrator Setup (Step by Step)

1. Create an OpenAI API key.
2. Put this in `.env`: `OPENAI_API_KEY=...`
3. Create a Gemini API key.
4. Put this in `.env`: `GEMINI_API_KEY=...`
5. Keep provider routing defaults for your preference (OpenAI primary, Gemini backup):
   - `ORCHESTRATOR_PRIMARY_PROVIDER=openai`
   - `ORCHESTRATOR_ENABLE_GEMINI_FALLBACK=true`
6. Optional model overrides:
   - `OPENAI_MODEL=gpt-4o` (default)
   - `GEMINI_MODEL=gemini-2.5-flash` (fallback default)
7. Optional tool-call loop cap:
   - `OPENAI_MAX_TOOL_ROUNDS=8`
8. Create a Fastino API key and add:
   - `FASTINO_API_KEY=...`
9. Keep Fastino guardrails defaults (or tune):
   - `FASTINO_GUARDRAILS_ENABLED=true`
   - `FASTINO_BASE_URL=https://api.fastino.ai`
   - `FASTINO_PII_THRESHOLD=0.35`
   - `FASTINO_ACTION_THRESHOLD=0.5`
   - `FASTINO_FAIL_MODE=open`
10. Create a Yutori API key and add:
   - `YUTORI_API_KEY=...`
11. Keep Yutori defaults (or tune):
   - `YUTORI_BASE_URL=https://api.yutori.com`
   - `YUTORI_POLL_SECONDS=3`
   - `YUTORI_TASK_TIMEOUT_SECONDS=180`
   - `YUTORI_HTTP_TIMEOUT_SECONDS=30`
   - `YUTORI_MAX_STEPS=75`
12. Create a Numeric API key and add:
   - `NUMERIC_API_KEY=...`
13. Keep Numeric defaults (or tune):
   - `NUMERIC_BASE_URL=https://api.numeric.io`
   - `NUMERIC_VARIANCE_PATH=/v1/variance/analysis`
   - `NUMERIC_TIMEOUT_SECONDS=20`
   - `NUMERIC_MATERIALITY_THRESHOLD_PCT=0.1`
   - `NUMERIC_FALLBACK_ENABLED=true`
14. Create a Tavily API key and add:
   - `TAVILY_API_KEY=...`
15. Keep Tavily defaults (or tune):
   - `TAVILY_BASE_URL=https://api.tavily.com`
   - `TAVILY_SEARCH_PATH=/search`
   - `TAVILY_TIMEOUT_SECONDS=20`
   - `TAVILY_TOPIC=news`
   - `TAVILY_SEARCH_DEPTH=basic`
   - `TAVILY_INCLUDE_ANSWER=basic`
   - `TAVILY_FALLBACK_ENABLED=true`
16. Create a Modulate API key and add:
   - `MODULATE_API_KEY=...`
17. Keep Modulate defaults (or tune):
   - `MODULATE_BASE_URL=https://api.modulate.ai`
   - `MODULATE_ANALYZE_PATH=/v1/velma/analyze`
   - `MODULATE_TIMEOUT_SECONDS=20`
   - `MODULATE_STRESS_THRESHOLD=0.6`
   - `MODULATE_FALLBACK_ENABLED=true`
18. Ensure GraphRAG and Senso credentials are configured if you want those tools active.
19. Run `run-diagnostic-orchestrator`.

## Optional Senso Publish

```bash
cd /Users/aditya/repos/hacks/airbyte-synthetic-data-pipeline
source .venv/bin/activate
build-agent-context \
  --input examples/synthetic_raw_bundle.json \
  --source-name airbyte_synthetic_source \
  --publish-to-senso \
  --senso-title-prefix "Synthetic Commerce"
```

## Environment Variables

- Airbyte: `AIRBYTE_SERVER_URL`, `AIRBYTE_BEARER_TOKEN` or `AIRBYTE_USERNAME` + `AIRBYTE_PASSWORD`, `AIRBYTE_WORKSPACE_ID`, `AIRBYTE_SOURCE_DEFINITION_ID`, `AIRBYTE_DESTINATION_ID`
- Senso: `SENSO_API_KEY`, `SENSO_BASE_URL`, `SENSO_POLL_SECONDS`, `SENSO_TIMEOUT_SECONDS`
- Neo4j/AWS: `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`, `NEO4J_VECTOR_INDEX`, `AWS_REGION`, `BEDROCK_EMBEDDING_MODEL_ID`
- Orchestrator/LLM: `ORCHESTRATOR_PRIMARY_PROVIDER`, `ORCHESTRATOR_ENABLE_GEMINI_FALLBACK`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_MAX_TOOL_ROUNDS`, `GEMINI_API_KEY`, `GEMINI_MODEL`
- Fastino Guardrails: `FASTINO_API_KEY`, `FASTINO_BASE_URL`, `FASTINO_GUARDRAILS_ENABLED`, `FASTINO_PII_THRESHOLD`, `FASTINO_ACTION_THRESHOLD`, `FASTINO_TIMEOUT_SECONDS`, `FASTINO_FAIL_MODE`
- Yutori Web Navigation: `YUTORI_API_KEY`, `YUTORI_BASE_URL`, `YUTORI_POLL_SECONDS`, `YUTORI_TASK_TIMEOUT_SECONDS`, `YUTORI_HTTP_TIMEOUT_SECONDS`, `YUTORI_MAX_STEPS`
- Numeric Finance: `NUMERIC_API_KEY`, `NUMERIC_BASE_URL`, `NUMERIC_VARIANCE_PATH`, `NUMERIC_TIMEOUT_SECONDS`, `NUMERIC_MATERIALITY_THRESHOLD_PCT`, `NUMERIC_FALLBACK_ENABLED`
- Tavily External Search: `TAVILY_API_KEY`, `TAVILY_BASE_URL`, `TAVILY_SEARCH_PATH`, `TAVILY_TIMEOUT_SECONDS`, `TAVILY_TOPIC`, `TAVILY_SEARCH_DEPTH`, `TAVILY_INCLUDE_ANSWER`, `TAVILY_FALLBACK_ENABLED`
- Modulate Voice Interface: `MODULATE_API_KEY`, `MODULATE_BASE_URL`, `MODULATE_ANALYZE_PATH`, `MODULATE_TIMEOUT_SECONDS`, `MODULATE_STRESS_THRESHOLD`, `MODULATE_FALLBACK_ENABLED`
