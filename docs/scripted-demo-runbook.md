# Scripted Demo Runbook (Engineering Incident Story)

This runbook is for engineering/support audiences:

> "Checkout API started returning HTTP 500 after deploy. Instead of paging people to manually triage for hours, the agent correlates logs, deploy metadata, internal chatter, and cloud status, then proposes a fix and incident update."

The demo stays resilient even without live provider keys when:
- `ORCHESTRATOR_ENABLE_LOCAL_DEMO_FALLBACK=true`
- `SPONSOR_MOCK_DATA_ENABLED=true`

---

## 0A. Deterministic Terminal Fallback

If UI/network is unstable, run:

```bash
python demo/run_incident_demo.py
```

This produces:
- incident evidence snapshot
- hypotheses + root cause
- mitigation actions + PR draft context
- output JSON at `demo/output/latest_incident_demo.json`

---

## 0. Pre-Demo Check (2 minutes)

- Open app: `https://silo-smasher.onrender.com`
- Confirm API badge is live.
- Run smoke prompt:
  - `Health check: summarize current incident risk in one line.`

---

## 1. Opening Narrative (20 seconds)

Use this line:

"Traditional dashboards detect incidents. Silo Smasher explains root cause and mitigation path automatically, using the same evidence an on-call engineer would collect manually."

---

## 2. Main Prompt

Run in chat:

`Checkout API started returning HTTP 500 after deploy. Find root cause, mitigation, and draft incident update.`

What to point to:
- **Summary**: impact + likely cause.
- **Hypotheses**: supported vs ruled out.
- **Evidence**:
  - incident snapshot (service, deploy, commit, endpoint)
  - logs/trace lines
  - internal incident messages
  - provider/cloud status note
- **Actions**: rollback/flag mitigation + PR draft direction.

---

## 3. Drill-Down Prompt

Run:

`Show strongest evidence that this is deploy regression and not cloud outage.`

Narrate:
- Stack trace points to recent commit path.
- Internal war-room messages align with deploy timestamp.
- Cloud/provider status does not show primary outage signal.

---

## 4. Proactive Comms Prompt

Run:

`Write the proactive incident update I should send to support and leadership.`

Narrate:
- Includes blast radius, current mitigation, and next ETA.
- Keeps non-engineering stakeholders aligned without waiting for full postmortem.

---

## 5. Close (15 seconds)

Use this line:

"In one flow, we moved from alert to evidence-backed root cause, generated mitigation actions, and prepared communication and PR direction."
