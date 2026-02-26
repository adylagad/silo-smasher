from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI, OpenAIError

from silo_smasher.guardrails import FastinoSafetyEngine

from .config import OrchestratorSettings
from .tools import DiagnosticToolRuntime


SYSTEM_PROMPT = """
You are the Diagnostic Data Explorer orchestrator.
Goal: explain why a business metric changed, not only what changed.

Operating rules:
1. Generate 2-4 plausible hypotheses first.
2. Use tools to test hypotheses with evidence.
3. Prefer grounded tool outputs over assumptions.
4. Return a concise executive brief.
5. If graph/system evidence is missing, use web navigation to retrieve the latest internal PDF report.
6. When revenue declines, use finance variance analysis to classify seasonal dip vs accounting anomaly.
7. If finance analysis indicates regional decline (for example Japan), search external economic news in the last 24 hours.
8. In voice-command mode, analyze user emotion/intent and prioritize summary mode when stress is detected.

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
                "Model providers unavailable; using latest local system-of-record summary."
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
                "Unable to complete model reasoning due to provider failures; check quota/rate limits."
            ),
            "confidence_overall": 0.0,
            "recommended_next_queries": [
                f"Retry question when provider quota is restored: {question}",
                "Inspect local context preview from fallback payload.",
            ],
            "local_context": local_context,
        }
