# Recommended Next Steps

Completed items were removed from this list:
- SQL structured query tool.
- Internal unstructured signal search.
- Proactive monitor endpoints + auto-trigger runtime.
- MCP server exposure.

Open high-leverage work:

---

## 1. The Scripted Demo Story

The demo runbook exists in `docs/scripted-demo-runbook.md`, but the data story is still generic.

To make the live narrative deterministic, add:

1. **A tailored synthetic bundle** — create `examples/uk_shipping_incident.json` where UK shipped orders drop sharply after a timestamp and are tied to one shipping partner.
2. **A scripted pipeline runner** — add `demo/run_demo.py` that loads this tailored bundle, runs context + graph + diagnosis, and prints an executive brief.
3. **A matching default demo prompt** — keep the prompt and expected result stable for presentations (`"MRR is down 15% this week in the UK. Why?"`).

---

## 2. Activate Real Sponsor API Keys

Some integrations still run in fallback mode when real keys are absent.

| Integration | What It Unlocks |
|---|---|
| **Senso** `SENSO_API_KEY` | Verified external ground-truth IDs and provenance |
| **Yutori** `YUTORI_API_KEY` | Real browser automation instead of placeholder browsing responses |
| **Numeric** `NUMERIC_API_KEY` | Real CFO-grade variance analysis responses |
| **Modulate** `MODULATE_API_KEY` | Real intent/emotion inference instead of local heuristic |

For judging demos, Numeric + Senso are the most visible upgrades.

---

## 3. Test Suite

There are still no committed tests. Add a minimal automated suite:

- `tests/test_normalize.py` for `normalize_raw_bundle()`.
- `tests/test_orchestrator_fallback.py` for provider failure + fallback behavior.
- `tests/test_health.py` for API liveness and stable JSON contract.
- `tests/test_monitoring.py` for `/monitor` create/check/stop behavior with local SQLite bootstrap.
- `tests/test_mcp_server.py` for MCP tool registration smoke checks.

Run with: `pytest tests/`
