from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic engineering-incident demo (500 after deploy)."
    )
    parser.add_argument(
        "--question",
        default=None,
        help="Optional override for incident question.",
    )
    parser.add_argument(
        "--output-file",
        default="demo/output/latest_incident_demo.json",
        help="Where to write incident demo output JSON.",
    )
    parser.add_argument(
        "--allow-live-provider",
        action="store_true",
        help="Allow live model/provider calls instead of deterministic fallback mode.",
    )
    return parser.parse_args()


def _load_incident_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Incident context must be JSON object: {path}")
    return payload


def _run_orchestrator(question: str) -> dict[str, Any]:
    from silo_smasher.orchestrator import DiagnosticOrchestrator, OrchestratorSettings

    orchestrator = DiagnosticOrchestrator(OrchestratorSettings.from_env())
    return orchestrator.run(question=question)


def _run_incident_snapshot_tool() -> dict[str, Any]:
    from silo_smasher.orchestrator.tools import DiagnosticToolRuntime

    runtime = DiagnosticToolRuntime()
    try:
        return runtime.call(
            "get_incident_context_snapshot",
            {
                "include_logs": True,
                "max_log_lines": 6,
                "include_cloud_events": True,
            },
        )
    finally:
        runtime.close()


def main() -> None:
    load_dotenv()
    args = _parse_args()

    incident_path = Path(
        os.getenv("INCIDENT_CONTEXT_PATH", "data/incident/http_500_after_deploy.json")
    )
    incident_path = (
        incident_path
        if incident_path.is_absolute()
        else (PROJECT_ROOT / incident_path).resolve()
    )
    if not incident_path.exists():
        raise RuntimeError(f"Incident context missing: {incident_path}")

    os.environ.setdefault(
        "INTERNAL_SIGNALS_PATH",
        str((PROJECT_ROOT / "data/internal_signals/incident_war_room_messages.json").resolve()),
    )
    os.environ.setdefault("INCIDENT_CONTEXT_PATH", str(incident_path))

    incident_payload = _load_incident_file(incident_path)
    question = str(
        args.question
        or incident_payload.get("default_question")
        or "Service is returning 500. Find root cause and mitigation."
    ).strip()
    if not question:
        raise RuntimeError("Question cannot be empty.")

    deterministic_keys = [
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "NUMERIC_API_KEY",
        "TAVILY_API_KEY",
    ]
    previous_env: dict[str, str | None] = {}
    if not args.allow_live_provider:
        for key_name in deterministic_keys:
            previous_env[key_name] = os.environ.get(key_name)
            os.environ.pop(key_name, None)
        previous_env["SPONSOR_MOCK_DATA_ENABLED"] = os.environ.get("SPONSOR_MOCK_DATA_ENABLED")
        previous_env["ORCHESTRATOR_ENABLE_LOCAL_DEMO_FALLBACK"] = os.environ.get(
            "ORCHESTRATOR_ENABLE_LOCAL_DEMO_FALLBACK"
        )
        os.environ["SPONSOR_MOCK_DATA_ENABLED"] = "true"
        os.environ["ORCHESTRATOR_ENABLE_LOCAL_DEMO_FALLBACK"] = "true"

    try:
        incident_snapshot = _run_incident_snapshot_tool()
        diagnostic = _run_orchestrator(question)
    finally:
        if not args.allow_live_provider:
            for key_name in deterministic_keys:
                previous = previous_env.get(key_name)
                if previous is None:
                    os.environ.pop(key_name, None)
                else:
                    os.environ[key_name] = previous
            sponsor_previous = previous_env.get("SPONSOR_MOCK_DATA_ENABLED")
            if sponsor_previous is None:
                os.environ.pop("SPONSOR_MOCK_DATA_ENABLED", None)
            else:
                os.environ["SPONSOR_MOCK_DATA_ENABLED"] = sponsor_previous
            local_demo_previous = previous_env.get("ORCHESTRATOR_ENABLE_LOCAL_DEMO_FALLBACK")
            if local_demo_previous is None:
                os.environ.pop("ORCHESTRATOR_ENABLE_LOCAL_DEMO_FALLBACK", None)
            else:
                os.environ["ORCHESTRATOR_ENABLE_LOCAL_DEMO_FALLBACK"] = local_demo_previous

    report = {
        "question": question,
        "incident_context": incident_snapshot,
        "diagnostic": diagnostic,
    }

    output_file = Path(args.output_file)
    output_file = output_file if output_file.is_absolute() else (PROJECT_ROOT / output_file).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    root_cause = diagnostic.get("most_likely_root_cause", "n/a")
    confidence = diagnostic.get("confidence_overall", "n/a")
    actions = diagnostic.get("actions", [])
    first_action = actions[0] if isinstance(actions, list) and actions else "n/a"
    print("Incident Demo")
    print("=============")
    print(f"Question: {question}")
    print(f"Root Cause: {root_cause}")
    print(f"Confidence: {confidence}")
    print(f"First Action: {first_action}")
    print(f"Output File: {output_file}")


if __name__ == "__main__":
    main()
