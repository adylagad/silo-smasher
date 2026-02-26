# Airbyte Synthetic Data Pipeline

Pipeline for three jobs:

1. Create/reuse a synthetic Airbyte source and run syncs.
2. Normalize raw records into deterministic `agent_ready_context` JSON (System of Record).
3. Load entities into Neo4j AuraDB and run GraphRAG with AWS Bedrock embeddings.

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
    pipeline/
      ground_truth.py
    cli/
      build_agent_context.py
      sync_graph_context.py
      query_graph_rag.py
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

