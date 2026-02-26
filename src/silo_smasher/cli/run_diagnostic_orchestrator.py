from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from silo_smasher.orchestrator import (
    DiagnosticOrchestrator,
    OrchestratorSettings,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run OpenAI diagnostic orchestrator with tool access to Neo4j GraphRAG and Senso."
        )
    )
    parser.add_argument("--question", required=True)
    parser.add_argument(
        "--context-file",
        default=None,
        help="Optional text/JSON file to include as extra context for the orchestrator.",
    )
    return parser.parse_args()


def _load_context(path_value: str | None) -> str | None:
    if not path_value:
        return None
    path = Path(path_value).expanduser().resolve()
    if not path.exists():
        raise RuntimeError(f"Context file not found: {path}")
    return path.read_text(encoding="utf-8")


def main() -> None:
    load_dotenv()
    args = _parse_args()
    settings = OrchestratorSettings.from_env()
    orchestrator = DiagnosticOrchestrator(settings)
    output = orchestrator.run(
        question=args.question,
        extra_context=_load_context(args.context_file),
    )
    print(json.dumps(output, indent=2, sort_keys=True, ensure_ascii=True))


if __name__ == "__main__":
    main()

