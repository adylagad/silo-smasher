from __future__ import annotations

from silo_smasher.orchestrator import DiagnosticOrchestrator, OrchestratorSettings


def test_orchestrator_returns_provider_failure_payload_when_demo_fallback_disabled(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("FASTINO_API_KEY", raising=False)

    monkeypatch.setenv("ORCHESTRATOR_ENABLE_LOCAL_DEMO_FALLBACK", "false")
    monkeypatch.setenv("ORCHESTRATOR_ENABLE_GEMINI_FALLBACK", "true")
    monkeypatch.setenv("ORCHESTRATOR_PRIMARY_PROVIDER", "openai")

    orchestrator = DiagnosticOrchestrator(OrchestratorSettings.from_env())
    result = orchestrator.run("Test fallback behavior when providers are unavailable.")

    assert result["error"] == "all_providers_failed"
    assert isinstance(result.get("attempts"), list)
    assert len(result["attempts"]) >= 1
    assert "fallback_response" in result
    assert isinstance(result["fallback_response"], dict)
