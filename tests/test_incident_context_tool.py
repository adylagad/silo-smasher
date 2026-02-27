from __future__ import annotations

from pathlib import Path

from silo_smasher.orchestrator.tools import DiagnosticToolRuntime


def test_incident_context_snapshot_tool_returns_expected_fields(monkeypatch) -> None:
    context_path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "incident"
        / "http_500_after_deploy.json"
    )
    monkeypatch.setenv("INCIDENT_CONTEXT_PATH", str(context_path))

    runtime = DiagnosticToolRuntime()
    try:
        payload = runtime.call(
            "get_incident_context_snapshot",
            {
                "include_logs": True,
                "max_log_lines": 2,
                "include_cloud_events": True,
            },
        )
    finally:
        runtime.close()

    assert payload["source"] == "local_incident_context"
    assert payload["scenario_id"] == "checkout_500_after_deploy"
    assert payload["service"]["name"] == "checkout-api"
    assert payload["deploy"]["deploy_id"] == "dep_20260227_0906"
    assert len(payload["log_excerpt"]) == 2
