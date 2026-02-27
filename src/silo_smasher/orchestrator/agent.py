from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI, OpenAIError

from silo_smasher.guardrails import FastinoSafetyEngine

from .config import OrchestratorSettings
from .tools import DiagnosticToolRuntime


SYSTEM_PROMPT = """
You are an Autonomous Incident Engineer for software and support teams.
Goal: explain why a production service degraded and recommend the fastest safe mitigation.

Operating rules:
1. Generate 2-4 plausible hypotheses first.
2. Use tools to test hypotheses with evidence.
3. Prefer grounded tool outputs over assumptions.
4. Use get_incident_context_snapshot for logs, deploy metadata, traces, infra events, and proposed PR context.
5. Correlate internal incident chatter with search_internal_communications.
6. Use run_sql_query for read-only validation when structured event data is available.
7. Check external status signals for cloud/vendor incidents before assigning root cause.
8. Return a concise incident brief with impact, root cause, mitigation, and next actions.
9. If no internal evidence is available, use web navigation for latest internal incident reports.
10. In voice-command mode, prioritize summary mode when stress is detected.

Final answer JSON schema:
{
  "metric_summary": "string",
  "hypotheses": [
    {
      "name": "string",
      "status": "supported|rejected|inconclusive",
      "confidence": 0.0,
      "evidence": ["string"]
    }
  ],
  "most_likely_root_cause": "string",
  "confidence_overall": 0.0,
  "recommended_next_queries": ["string"]
}
""".strip()


class DiagnosticOrchestrator:
    def __init__(self, settings: OrchestratorSettings):
        self._settings = settings
        openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        self._openai_client: OpenAI | None = (
            OpenAI(api_key=openai_key) if openai_key and openai_key not in {"__MISSING__", "__SET_ME__"} else None
        )
        self._safety_engine = FastinoSafetyEngine.from_env()

    def run(self, question: str, extra_context: str | None = None) -> dict[str, Any]:
        runtime = DiagnosticToolRuntime()
        safety_report: dict[str, Any] = {"input_redaction": None, "tool_checks": []}
        try:
            prompt = question.strip()
            if extra_context:
                prompt = f"{prompt}\n\nContext:\n{extra_context.strip()}"

            redaction = self._safety_engine.redact_sensitive_text(prompt)
            prompt = redaction.sanitized_text
            safety_report["input_redaction"] = redaction.to_dict()

            attempts: list[dict[str, Any]] = []
            for provider in self._provider_order():
                if provider == "openai":
                    payload, error = self._run_with_openai(
                        prompt=prompt,
                        runtime=runtime,
                        safety_report=safety_report,
                    )
                elif provider == "gemini":
                    payload, error = self._run_with_gemini(
                        prompt=prompt,
                        runtime=runtime,
                        safety_report=safety_report,
                    )
                else:
                    payload, error = None, {"error": "unknown_provider", "provider": provider}

                if error is None and payload is not None:
                    payload["_provider"] = provider
                    payload["_safety"] = safety_report
                    return payload

                attempts.append(
                    {
                        "provider": provider,
                        "error": error or {"error": "unknown_failure"},
                    }
                )

            if self._settings.enable_local_demo_fallback:
                payload = self._local_demo_response(runtime=runtime, question=question, attempts=attempts)
                payload["_provider"] = "local_demo"
                payload["_safety"] = safety_report
                return payload

            return {
                "error": "all_providers_failed",
                "attempts": attempts,
                "_safety": safety_report,
                "fallback_response": self._local_provider_fallback(runtime, question),
            }
        finally:
            runtime.close()

    def _provider_order(self) -> list[str]:
        primary = self._settings.primary_provider
        if primary not in {"openai", "gemini"}:
            primary = "openai"

        order = [primary]
        if self._settings.enable_gemini_fallback:
            if primary == "openai":
                order.append("gemini")
            elif primary == "gemini":
                order.append("openai")
        return order

    def _run_with_openai(
        self,
        prompt: str,
        runtime: DiagnosticToolRuntime,
        safety_report: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        if self._openai_client is None:
            return None, {"error": "openai_api_key_missing"}
        try:
            response = self._openai_client.responses.create(
                model=self._settings.openai_model,
                instructions=SYSTEM_PROMPT,
                input=prompt,
                tools=runtime.schemas(),
            )
        except OpenAIError as exc:
            return None, self._openai_error_payload(exc)

        for _ in range(self._settings.max_tool_rounds):
            function_calls = [
                item
                for item in response.output
                if getattr(item, "type", "") == "function_call"
            ]
            if not function_calls:
                return self._final_payload_from_openai(response), None

            tool_outputs = []
            for call in function_calls:
                try:
                    raw_args = call.arguments
                    if isinstance(raw_args, str):
                        arguments = json.loads(raw_args or "{}")
                    elif isinstance(raw_args, dict):
                        arguments = raw_args
                    else:
                        arguments = {}
                except (json.JSONDecodeError, TypeError):
                    arguments = {}

                tool_result = self._run_tool_with_guardrails(
                    runtime=runtime,
                    tool_name=call.name,
                    arguments=arguments,
                    provider="openai",
                    safety_report=safety_report,
                    call_id=call.call_id,
                )
                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(tool_result, ensure_ascii=True),
                    }
                )

            try:
                response = self._openai_client.responses.create(
                    model=self._settings.openai_model,
                    instructions=SYSTEM_PROMPT,
                    previous_response_id=response.id,
                    input=tool_outputs,
                    tools=runtime.schemas(),
                )
            except OpenAIError as exc:
                return None, self._openai_error_payload(exc)

        return None, {
            "error": "max_tool_rounds_reached",
            "model": self._settings.openai_model,
        }

    def _run_with_gemini(
        self,
        prompt: str,
        runtime: DiagnosticToolRuntime,
        safety_report: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        try:
            from google import genai
            from google.genai import types
        except Exception as exc:
            return None, {"error": "gemini_sdk_missing", "detail": str(exc)}

        api_key = self._settings.gemini_api_key
        if not api_key:
            return None, {"error": "gemini_api_key_missing"}

        try:
            if os.getenv("GEMINI_API_KEY") and os.getenv("GOOGLE_API_KEY"):
                os.environ.pop("GOOGLE_API_KEY", None)
            client = genai.Client(api_key=api_key)
            function_declarations = [
                types.FunctionDeclaration(
                    name=spec["name"],
                    description=spec.get("description"),
                    parametersJsonSchema=spec.get("parameters", {}),
                )
                for spec in runtime.schemas()
            ]
            config = types.GenerateContentConfig(
                systemInstruction=SYSTEM_PROMPT,
                tools=[types.Tool(functionDeclarations=function_declarations)],
                automaticFunctionCalling=types.AutomaticFunctionCallingConfig(disable=True),
            )

            contents: list[types.Content] = [
                types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
            ]

            for _ in range(self._settings.max_tool_rounds):
                response = client.models.generate_content(
                    model=self._settings.gemini_model,
                    contents=contents,
                    config=config,
                )

                function_calls = list(response.function_calls or [])
                if not function_calls:
                    return self._final_payload_from_gemini(response), None

                model_parts = []
                user_response_parts = []
                for call in function_calls:
                    call_name = str(call.name or "")
                    call_args = dict(call.args or {})
                    if not call_name:
                        continue
                    model_parts.append(
                        types.Part.from_function_call(name=call_name, args=call_args)
                    )
                    tool_result = self._run_tool_with_guardrails(
                        runtime=runtime,
                        tool_name=call_name,
                        arguments=call_args,
                        provider="gemini",
                        safety_report=safety_report,
                    )
                    user_response_parts.append(
                        types.Part.from_function_response(
                            name=call_name,
                            response=tool_result,
                        )
                    )

                if model_parts:
                    contents.append(types.Content(role="model", parts=model_parts))
                if user_response_parts:
                    contents.append(types.Content(role="user", parts=user_response_parts))

            return None, {
                "error": "max_tool_rounds_reached",
                "model": self._settings.gemini_model,
            }
        except Exception as exc:
            return None, {
                "error": "gemini_request_failed",
                "error_type": exc.__class__.__name__,
                "detail": str(exc),
            }

    @staticmethod
    def _final_payload_from_openai(response: Any) -> dict[str, Any]:
        text = getattr(response, "output_text", None)
        if text:
            return DiagnosticOrchestrator._parse_json_or_text(text)

        output_items = []
        for item in getattr(response, "output", []):
            if getattr(item, "type", "") != "message":
                continue
            content = getattr(item, "content", [])
            for block in content:
                if getattr(block, "type", "") == "output_text":
                    output_items.append(getattr(block, "text", ""))
        joined = "\n".join([t for t in output_items if t])
        if not joined:
            return {"error": "empty_model_output"}
        return DiagnosticOrchestrator._parse_json_or_text(joined)

    @staticmethod
    def _final_payload_from_gemini(response: Any) -> dict[str, Any]:
        text = getattr(response, "text", None)
        if text:
            return DiagnosticOrchestrator._parse_json_or_text(text)

        parts = getattr(response, "parts", None) or []
        text_chunks = []
        for part in parts:
            part_text = getattr(part, "text", None)
            if part_text:
                text_chunks.append(part_text)
        joined = "\n".join(text_chunks).strip()
        if not joined:
            return {"error": "empty_model_output"}
        return DiagnosticOrchestrator._parse_json_or_text(joined)

    @staticmethod
    def _parse_json_or_text(text: str) -> dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw_output_text": text}

    @staticmethod
    def _openai_error_payload(exc: OpenAIError) -> dict[str, Any]:
        return {
            "error": "openai_request_failed",
            "error_type": exc.__class__.__name__,
            "detail": str(exc),
        }

    def _run_tool_with_guardrails(
        self,
        runtime: DiagnosticToolRuntime,
        tool_name: str,
        arguments: dict[str, Any],
        provider: str,
        safety_report: dict[str, Any],
        call_id: str | None = None,
    ) -> dict[str, Any]:
        action_payload = {
            "tool_name": tool_name,
            "arguments": arguments,
        }
        action_text = json.dumps(action_payload, sort_keys=True, ensure_ascii=True)
        decision = self._safety_engine.evaluate_action(action_text)
        check_record = decision.to_dict()
        check_record["provider"] = provider
        check_record["tool_name"] = tool_name
        check_record["call_id"] = call_id
        safety_report["tool_checks"].append(check_record)

        if not decision.allowed:
            return {
                "error": "blocked_by_guardrails",
                "tool_name": tool_name,
                "reason": decision.reason,
                "category": decision.category,
            }

        return runtime.call(tool_name, arguments)

    def _local_demo_response(
        self,
        *,
        runtime: DiagnosticToolRuntime,
        question: str,
        attempts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        incident_context = runtime.call(
            "get_incident_context_snapshot",
            {
                "include_logs": True,
                "max_log_lines": 8,
                "include_cloud_events": True,
            },
        )
        internal_signals = runtime.call(
            "search_internal_communications",
            {
                "query": f"{question} http 500 deploy rollback stacktrace incident",
                "hours_back": 72,
                "max_results": 6,
            },
        )
        external_news = runtime.call(
            "search_external_economic_news",
            {
                "country": "United States",
                "query": "AWS us-east-1 outage and payment API incidents in the last 24 hours",
                "hours_back": 24,
                "max_results": 5,
            },
        )
        graph_context = {
            "source": "skipped_in_local_demo",
            "message": "Graph query skipped in deterministic local demo mode to avoid external dependency noise.",
        }
        local_context = runtime.call(
            "get_latest_system_record_entries",
            {"count": 1, "include_context_preview": True},
        )
        incident_service = (
            incident_context.get("service", {})
            if isinstance(incident_context, dict) and isinstance(incident_context.get("service"), dict)
            else {}
        )
        incident_deploy = (
            incident_context.get("deploy", {})
            if isinstance(incident_context, dict) and isinstance(incident_context.get("deploy"), dict)
            else {}
        )
        incident_analysis = (
            incident_context.get("analysis", {})
            if isinstance(incident_context, dict) and isinstance(incident_context.get("analysis"), dict)
            else {}
        )
        incident_pr = (
            incident_context.get("proposed_pr", {})
            if isinstance(incident_context, dict) and isinstance(incident_context.get("proposed_pr"), dict)
            else {}
        )
        incident_logs = (
            incident_context.get("log_excerpt", [])
            if isinstance(incident_context, dict) and isinstance(incident_context.get("log_excerpt"), list)
            else []
        )
        infra_events = (
            incident_context.get("infra_events", [])
            if isinstance(incident_context, dict) and isinstance(incident_context.get("infra_events"), list)
            else []
        )

        internal_results = (
            internal_signals.get("results", [])
            if isinstance(internal_signals, dict) and isinstance(internal_signals.get("results"), list)
            else []
        )
        external_results = (
            external_news.get("results", [])
            if isinstance(external_news, dict) and isinstance(external_news.get("results"), list)
            else []
        )

        top_internal = internal_results[0] if internal_results else {}
        top_external = external_results[0] if external_results else {}
        top_internal_text = (
            str(top_internal.get("text", "")).strip()
            if isinstance(top_internal, dict)
            else ""
        )
        top_external_title = (
            str(top_external.get("title", "")).strip()
            if isinstance(top_external, dict)
            else ""
        )
        root_cause_text = str(incident_analysis.get("primary_cause", "")).strip()
        confidence_value = incident_analysis.get("confidence")
        confidence_overall = (
            float(confidence_value)
            if isinstance(confidence_value, (int, float))
            else 0.87
        )

        deploy_id = str(incident_deploy.get("deploy_id", "unknown_deploy")).strip()
        commit_sha = str(incident_deploy.get("commit_sha", "unknown_commit")).strip()
        service_name = str(incident_service.get("name", "unknown_service")).strip()
        endpoint = str(incident_service.get("endpoint", "unknown_endpoint")).strip()
        top_log_line = str(incident_logs[0]).strip() if incident_logs else ""
        top_infra_detail = (
            str(infra_events[0].get("detail", "")).strip()
            if infra_events and isinstance(infra_events[0], dict)
            else ""
        )
        hypothesis_deploy_status = (
            "supported" if root_cause_text and commit_sha != "unknown_commit" else "inconclusive"
        )
        hypothesis_deploy_confidence = (
            max(0.75, min(confidence_overall, 0.96))
            if hypothesis_deploy_status == "supported"
            else 0.48
        )
        hypothesis_external_status = "rejected" if top_infra_detail else "inconclusive"
        hypothesis_external_confidence = 0.72 if hypothesis_external_status == "rejected" else 0.39
        hypothesis_data_status = "supported" if top_log_line else "inconclusive"
        hypothesis_data_confidence = 0.84 if hypothesis_data_status == "supported" else 0.44

        metric_summary = (
            "Demo mode: incident telemetry, logs, deploy metadata, and internal comms indicate "
            f"an application-level regression in {service_name}."
        )
        root_cause = (
            root_cause_text
            or (
                f"{service_name} started returning HTTP 500 on {endpoint} after deploy {deploy_id} "
                f"({commit_sha}) due to a serializer null dereference."
            )
        )
        brief = (
            f"{metric_summary} Deploy {deploy_id} / commit {commit_sha} is the strongest suspect. "
            f"Endpoint impacted: {endpoint}. "
            f"Top internal signal: {top_internal_text or 'No internal message match found.'} "
            f"Cloud context: {top_infra_detail or top_external_title or 'No active cloud outage signal detected.'}"
        )

        return {
            "mode": "local_demo_fallback",
            "degraded_mode": True,
            "metric_summary": metric_summary,
            "brief": brief,
            "hypotheses": [
                {
                    "name": "Latest deploy introduced an application regression that caused HTTP 500s.",
                    "status": hypothesis_deploy_status,
                    "confidence": hypothesis_deploy_confidence,
                    "evidence": [
                        f"Internal matches found: {len(internal_results)}",
                        f"Deploy: {deploy_id} ({commit_sha})",
                        top_log_line or "No direct stack trace was found in incident logs.",
                    ],
                },
                {
                    "name": "Cloud provider outage is the primary cause.",
                    "status": hypothesis_external_status,
                    "confidence": hypothesis_external_confidence,
                    "evidence": [
                        top_infra_detail or "No provider-status event found in incident context.",
                        top_external_title or "No external status headline found in search output.",
                        (
                            str(external_news.get("answer", ""))
                            if isinstance(external_news, dict)
                            else "External news tool unavailable."
                        ),
                    ],
                },
                {
                    "name": "Root cause is visible in logs/traces and can be fixed with a code patch.",
                    "status": hypothesis_data_status,
                    "confidence": hypothesis_data_confidence,
                    "evidence": [
                        top_log_line or "No stack trace evidence available.",
                        f"Proposed branch: {incident_pr.get('branch', 'auto/fix-checkout-null-currency')}",
                    ],
                },
            ],
            "most_likely_root_cause": root_cause,
            "confidence_overall": confidence_overall,
            "recommended_next_queries": [
                "Query error counts by endpoint and release version for the last 60 minutes.",
                "Validate hotfix by replaying failing payload fixtures from incident logs.",
                "Track p95 latency and 500 rate for 30 minutes after mitigation rollout.",
            ],
            "actions": [
                (
                    f"Create PR draft '{incident_pr.get('title', 'Guard null currency metadata in serializer')}' "
                    f"on branch {incident_pr.get('branch', 'auto/fix-checkout-null-currency')}."
                ),
                "Enable rollback/fallback flag immediately to reduce customer impact.",
                (
                    "Send proactive incident update: "
                    + str(
                        incident_context.get(
                            "proactive_message_template",
                            "Service degradation detected, mitigation in progress.",
                        )
                    )
                ),
            ],
            "tool_outputs": {
                "incident_context": incident_context,
                "internal_signals": internal_signals,
                "external_news": external_news,
                "graph_context": graph_context,
                "local_context": local_context,
            },
            "provider_attempts": attempts,
        }

    @staticmethod
    def _local_provider_fallback(
        runtime: DiagnosticToolRuntime,
        question: str,
    ) -> dict[str, Any]:
        local_context = runtime.call(
            "get_latest_system_record_entries",
            {"count": 1, "include_context_preview": True},
        )
        return {
            "source": "local_fallback",
            "metric_summary": (
                "Model providers unavailable; using local incident/context fallback data."
            ),
            "hypotheses": [
                {
                    "name": "Provider availability issue",
                    "status": "inconclusive",
                    "confidence": 0.0,
                    "evidence": [
                        "Primary and fallback model providers failed in this run.",
                    ],
                }
            ],
            "most_likely_root_cause": (
                "Unable to complete model reasoning due to provider failures; verify model quotas and retry."
            ),
            "confidence_overall": 0.0,
            "recommended_next_queries": [
                f"Retry question when provider quota is restored: {question}",
                "Inspect local context preview from fallback payload.",
            ],
            "local_context": local_context,
        }
