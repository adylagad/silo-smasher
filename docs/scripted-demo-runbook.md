# Scripted Demo Runbook (Section 1 Story)

This runbook is aligned to **`## 1. The Scripted Demo Story`** in `docs/next-steps.md`:

> "80% of the MRR drop is from customers using a specific UK shipping partner. A UK postal strike started this morning."

The current implementation is demo-safe even without provider keys because `ORCHESTRATOR_ENABLE_LOCAL_DEMO_FALLBACK=true` and `SPONSOR_MOCK_DATA_ENABLED=true`.

---

## 0A. Deterministic Terminal Fallback (single command)

If the UI/network is unstable during demo, run:

```bash
python demo/run_demo.py
```

This command:
- loads `examples/uk_shipping_incident.json`
- builds system-of-record artifacts under `demo/output/system_of_record`
- runs internal signals + variance + external context tools
- runs orchestrator in deterministic local-demo mode by default
- writes final output to `demo/output/latest_demo_brief.json`

Use this line while showing terminal output:

"In deterministic mode, the same input always produces the same evidence-backed root-cause brief."

---

## 0. Pre-Demo Check (2 minutes)

- Open app: `https://silo-smasher.onrender.com`
- Confirm the API status badge is live.
- Open chat and run a quick smoke prompt:
  - `Health check: explain current metric risk in one line.`

If the provider APIs are down/quota-limited, the app still returns a full fallback investigation.

---

## 1. Opening Narrative (20-30 seconds)

Use this line:

"Most BI tools tell you **what** changed. Silo Smasher tells you **why** by combining SQL, graph context, internal communications, and external signals in one autonomous loop."

---

## 2. Main Prompt (Core Story)

In the chat panel, run:

`MRR is down 15% this week in the UK. Find the root cause using SQL, internal communications, and external signals.`

### What to point at on screen

- **Summary card**: executive-level explanation.
- **Findings cards**: confidence-scored hypotheses.
- **Evidence panel**:
  - `SQL` chips: purchased / returned / carted counts.
  - `Internal Signals`: top Slack/Jira-like incident messages with channel and timestamp.
- **Recommended Actions**: operational next steps.

Speaker line:

"This is not a single-model guess. You can see the SQL evidence and internal incident chatter side-by-side."

---

## 3. Evidence Drill-Down Prompt

Run:

`Show only the strongest evidence for UK checkout degradation with SQL and internal incident messages.`

### Narrate this

- "SQL shows behavior change in transaction states."
- "Internal communication confirms checkout bug + logistics delay timeline."
- "That timeline is exactly what explains the revenue drop."

---

## 4. External Context Prompt

Run:

`Check whether this UK revenue dip aligns with outside-world economic or logistics signals in the last 24 hours.`

Narrate:

- "Now we validate whether this is only internal or also market-driven."
- "The external signal layer prevents false confidence from internal-only data."

---

## 5. Close (15 seconds)

Use this line:

"In one interaction, we moved from anomaly to root-cause with confidence and actionability, across structured data, graph links, internal unstructured signals, and external context."

---

## 6. Judge Q&A Quick Answers

### Q: "How do you know it actually used SQL and Slack-like data?"
A: "The Evidence panel exposes both live SQL aggregates and internal communication hits directly in the UI."

### Q: "What if sponsor APIs fail during demo?"
A: "The app runs in resilient demo mode with deterministic mock payloads plus local fallback, so the full flow still works."

### Q: "What changes when real keys are available?"
A: "Disable mock/demo fallback and the same workflow executes against live provider APIs without changing the UI."

---

## 7. Optional Backup Script (if network is unstable)

If the UI is slow, keep the same story and run one concise prompt:

`MRR down 15% UK this week. Give me root cause, evidence, and actions.`

Then point to:

- Summary
- Findings
- Evidence panel (SQL + Internal Signals)
- Actions

This preserves the full narrative in under 60 seconds.
