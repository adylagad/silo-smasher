from __future__ import annotations

import json
from typing import Any

from openai import OpenAI, OpenAIError

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
        self._client = OpenAI()

    def run(self, question: str, extra_context: str | None = None) -> dict[str, Any]:
        runtime = DiagnosticToolRuntime()
        try:
            prompt = question.strip()
            if extra_context:
                prompt = f"{prompt}\n\nContext:\n{extra_context.strip()}"

            try:
                response = self._client.responses.create(
                    model=self._settings.openai_model,
                    instructions=SYSTEM_PROMPT,
                    input=prompt,
                    tools=runtime.schemas(),
                )
            except OpenAIError as exc:
                return self._openai_error_payload(exc)

            for _ in range(self._settings.max_tool_rounds):
                function_calls = [
                    item
                    for item in response.output
                    if getattr(item, "type", "") == "function_call"
                ]
                if not function_calls:
                    return self._final_payload(response)

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
                    tool_result = runtime.call(call.name, arguments)
                    tool_outputs.append(
                        {
                            "type": "function_call_output",
                            "call_id": call.call_id,
                            "output": json.dumps(tool_result, ensure_ascii=True),
                        }
                    )

                try:
                    response = self._client.responses.create(
                        model=self._settings.openai_model,
                        instructions=SYSTEM_PROMPT,
                        previous_response_id=response.id,
                        input=tool_outputs,
                        tools=runtime.schemas(),
                    )
                except OpenAIError as exc:
                    return self._openai_error_payload(exc)

            return {
                "error": "max_tool_rounds_reached",
                "model": self._settings.openai_model,
            }
        finally:
            runtime.close()

    @staticmethod
    def _final_payload(response: Any) -> dict[str, Any]:
        text = getattr(response, "output_text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"raw_output_text": text}

        output_items = []
        for item in getattr(response, "output", []):
            item_type = getattr(item, "type", "")
            if item_type == "message":
                content = getattr(item, "content", [])
                for block in content:
                    if getattr(block, "type", "") == "output_text":
                        output_items.append(getattr(block, "text", ""))
        joined = "\n".join([t for t in output_items if t])
        if not joined:
            return {"error": "empty_model_output"}
        try:
            return json.loads(joined)
        except json.JSONDecodeError:
            return {"raw_output_text": joined}

    @staticmethod
    def _openai_error_payload(exc: OpenAIError) -> dict[str, Any]:
        return {
            "error": "openai_request_failed",
            "error_type": exc.__class__.__name__,
            "detail": str(exc),
        }
