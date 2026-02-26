from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from airbyte_synthetic_data_pipeline.pipeline import run_ground_truth_pipeline


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize raw records into agent-ready context and optionally publish to Senso."
    )
    parser.add_argument("--input", required=True, help="Path to raw JSON bundle file.")
    parser.add_argument(
        "--output-root",
        default="data/system_of_record",
        help="Root directory for persisted system-of-record artifacts.",
    )
    parser.add_argument("--source-name", default="airbyte_synthetic_source")
    parser.add_argument("--workspace-id", default=None)
    parser.add_argument("--connection-id", default=None)
    parser.add_argument(
        "--publish-to-senso",
        action="store_true",
        help="Publish raw snapshot and normalized context to Senso.",
    )
    parser.add_argument(
        "--senso-title-prefix",
        default="Synthetic Commerce",
        help="Prefix used in Senso content titles.",
    )
    return parser.parse_args()


def _optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if value.strip() == "":
        return None
    return value


def main() -> None:
    load_dotenv()
    args = _parse_args()

    summary = run_ground_truth_pipeline(
        input_path=Path(args.input).expanduser().resolve(),
        output_root=Path(args.output_root).expanduser().resolve(),
        source_name=args.source_name,
        workspace_id=_optional(args.workspace_id),
        connection_id=_optional(args.connection_id),
        publish_to_senso=args.publish_to_senso,
        senso_title_prefix=args.senso_title_prefix,
    )
    print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=True))


if __name__ == "__main__":
    main()

