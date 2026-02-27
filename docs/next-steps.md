# Recommended Next Steps (Engineering Incident Direction)

The product is now positioned as an **Autonomous Incident Engineer**.  
The highest-leverage next work is below, ordered by impact.

---

## 1. Live Incident Data Connectors (Logs / Deploys / Traces)

Current `get_incident_context_snapshot` reads deterministic local JSON.  
Next, wire real sources behind feature flags:

- Logs: Datadog / CloudWatch / Elastic query adapter.
- Deploys: GitHub/GitLab deploy metadata + commit linkage.
- Traces: OpenTelemetry/Jaeger span evidence.

Outcome: agent conclusions are anchored to real production evidence, not only mock/demo context.

---

## 2. PR Automation Path (Draft + Safe Guardrails)

Current flow recommends PR details in output.  
Next, actually create a draft PR safely:

- Add `create_hotfix_pr_draft` tool (default disabled).
- Require guardrail policy checks for branch/file allowlist.
- Attach evidence bundle in PR description (logs, traces, hypothesis summary).

Outcome: incident-to-fix loop shortens from hours to minutes.

---

## 3. Proactive Incident Messaging

Current flow can propose proactive messaging text.  
Next, wire outbound channels:

- Slack incident channel webhook.
- PagerDuty note update.
- Status-page draft payload.

Outcome: support/leadership gets immediate, consistent updates without manual drafting.

---

## 4. Incident Evaluation Harness

Add repeatable scoring for trust:

- Golden incident cases (500 after deploy, DB pool exhaustion, dependency outage).
- Expected root-cause labels + confidence range.
- Precision/recall style scoreboard for hypotheses and mitigations.

Outcome: measurable quality bar for every change.

---

## 5. Full Slack/Jira Live Mode

Current implementation uses local synthetic incident messages.  
Next, add real connectors:

- Slack read-only history (`channels:history`, scoped).
- Jira incident ticket fetch and timeline correlation.

Outcome: stronger multi-silo evidence during real outages.

---

## 6. Operator UX Improvements

Focus the UI further on on-call workflows:

- Incident timeline strip (alert -> deploy -> fix).
- One-click "Generate stakeholder update".
- One-click "Prepare hotfix PR" (guarded).

Outcome: demo and production workflows align with engineering support teams.

---

## 7. MCP Expansion for Engineering Hosts

Expose incident tools over MCP for IDE agents:

- `get_incident_context_snapshot`
- `search_internal_communications`
- `query_graph_connections`
- future `create_hotfix_pr_draft` (guarded)

Outcome: Claude/Cursor/Codex can use Silo Smasher as an incident backend.
