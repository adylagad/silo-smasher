# Airbyte Synthetic Data Pipeline

Pipeline for two jobs:

1. Create/reuse a synthetic Airbyte source and run syncs.
2. Normalize raw records into deterministic `agent_ready_context` JSON and optionally publish both raw + normalized documents to Senso as a verifiable System of Record.

## Project Layout

```text
airbyte-synthetic-data-pipeline/
  data/system_of_record/
    raw_snapshots/
    agent_context/
    receipts/
    manifest.jsonl                # generated on runs
  examples/
    synthetic_raw_bundle.json     # sample raw input
  src/airbyte_synthetic_data_pipeline/
    context/
      normalize.py                # raw -> agent_ready_context
      schemas.py                  # schema metadata
    senso/
      client.py                   # Senso API wrapper
      publish.py                  # upload + verification receipt
    pipeline/
      ground_truth.py             # orchestration
    cli/
      build_agent_context.py      # main context CLI
    synthetic_sync.py             # Airbyte setup/sync CLI
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
python -m airbyte_synthetic_data_pipeline.cli.build_agent_context \
  --input examples/synthetic_raw_bundle.json \
  --source-name airbyte_synthetic_source
```

Outputs are written under `data/system_of_record/`:

- `raw_snapshots/*.json`
- `agent_context/*.json`
- `manifest.jsonl`

Accepted input formats:

- Bundle JSON with keys `users`, `products`, `purchases`
- Airbyte message JSON (`RECORD` messages), either as a top-level list or as `{ "messages": [...] }`

## Publish to Senso (Ground Truth Ledger)

```bash
cd /Users/aditya/repos/hacks/airbyte-synthetic-data-pipeline
source .venv/bin/activate
python -m airbyte_synthetic_data_pipeline.cli.build_agent_context \
  --input examples/synthetic_raw_bundle.json \
  --source-name airbyte_synthetic_source \
  --publish-to-senso \
  --senso-title-prefix "Synthetic Commerce"
```

When `--publish-to-senso` is enabled:

- raw snapshot is uploaded to Senso
- normalized context is uploaded to Senso
- each upload is polled until `processing_status=completed`
- returned context text hash is compared to local JSON hash
- receipt is written to `data/system_of_record/receipts/*.json`

This receipt is your auditable reference if an agent output later diverges.

## Senso Setup (Step by Step)

1. Get an API key from your Senso authorised contact (or request one via Senso support).
2. Open `/Users/aditya/repos/hacks/airbyte-synthetic-data-pipeline/.env`.
3. Set:
   - `SENSO_API_KEY=<your_key>`
   - `SENSO_BASE_URL=https://sdk.senso.ai/api/v1` (default; change only if your tenant uses a different host)
4. Keep polling defaults unless you need slower/faster checks:
   - `SENSO_POLL_SECONDS=2`
   - `SENSO_TIMEOUT_SECONDS=120`
5. Run a publish command with `--publish-to-senso`.
6. Confirm the generated receipt has:
   - `verification.is_match = true`
   - populated `raw_content.id` and `context_content.id`

## Environment Variables

- `AIRBYTE_SERVER_URL`
- `AIRBYTE_BEARER_TOKEN` or `AIRBYTE_USERNAME` + `AIRBYTE_PASSWORD`
- `AIRBYTE_WORKSPACE_ID` (optional)
- `AIRBYTE_SOURCE_DEFINITION_ID` (required for source creation)
- `AIRBYTE_DESTINATION_ID` (needed for sync)
- `SENSO_API_KEY` (required for Senso publish)
- `SENSO_BASE_URL` (optional)
- `SENSO_POLL_SECONDS` (optional)
- `SENSO_TIMEOUT_SECONDS` (optional)
