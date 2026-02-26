from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from airbyte_synthetic_data_pipeline.context import normalize_raw_bundle
from airbyte_synthetic_data_pipeline.senso import (
    SensoClient,
    SensoConfig,
    publish_system_of_record,
)


def _timestamp_label() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _compute_sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _bundle_from_airbyte_messages(messages: list[Any]) -> dict[str, Any]:
    bundle: dict[str, list[dict[str, Any]]] = {
        "users": [],
        "products": [],
        "purchases": [],
    }
    for message in messages:
        if not isinstance(message, dict):
            continue
        message_type = str(message.get("type", "")).lower()
        if message_type != "record":
            continue
        record = message.get("record")
        if not isinstance(record, dict):
            continue
        stream = str(record.get("stream", "")).lower()
        data = record.get("data")
        if stream in bundle and isinstance(data, dict):
            bundle[stream].append(data)
    return bundle


def _coerce_bundle(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        if isinstance(payload.get("messages"), list):
            return _bundle_from_airbyte_messages(payload["messages"])
        if any(key in payload for key in ("users", "products", "purchases")):
            return {
                "users": payload.get("users", []) if isinstance(payload.get("users"), list) else [],
                "products": payload.get("products", []) if isinstance(payload.get("products"), list) else [],
                "purchases": payload.get("purchases", []) if isinstance(payload.get("purchases"), list) else [],
            }
    if isinstance(payload, list):
        return _bundle_from_airbyte_messages(payload)
    raise RuntimeError(
        "Input JSON must be either a bundle object (users/products/purchases) or Airbyte record messages."
    )


def _load_json_file(path: Path) -> tuple[dict[str, Any], bytes]:
    raw_bytes = path.read_bytes()
    payload = json.loads(raw_bytes.decode("utf-8"))
    return _coerce_bundle(payload), raw_bytes


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True, ensure_ascii=True) + "\n")


def run_ground_truth_pipeline(
    input_path: Path,
    output_root: Path,
    source_name: str,
    workspace_id: Optional[str],
    connection_id: Optional[str],
    publish_to_senso: bool,
    senso_title_prefix: str,
) -> dict[str, Any]:
    raw_bundle, raw_bytes = _load_json_file(input_path)
    input_sha256 = _compute_sha256(raw_bytes)
    timestamp = _timestamp_label()
    short_hash = input_sha256[:10]

    normalized_context = normalize_raw_bundle(
        raw_bundle=raw_bundle,
        source_metadata={
            "source_name": source_name,
            "workspace_id": workspace_id,
            "connection_id": connection_id,
            "input_sha256": input_sha256,
        },
    )

    raw_snapshot_path = output_root / "raw_snapshots" / f"raw_{timestamp}_{short_hash}.json"
    context_path = output_root / "agent_context" / f"context_{timestamp}_{short_hash}.json"
    receipt_path = output_root / "receipts" / f"receipt_{timestamp}_{short_hash}.json"
    manifest_path = output_root / "manifest.jsonl"

    _write_json(raw_snapshot_path, raw_bundle)
    _write_json(context_path, normalized_context)

    summary: dict[str, Any] = {
        "timestamp": timestamp,
        "input_path": str(input_path),
        "input_sha256": input_sha256,
        "raw_snapshot_path": str(raw_snapshot_path),
        "context_path": str(context_path),
        "manifest_path": str(manifest_path),
        "senso_publication": None,
    }

    if publish_to_senso:
        senso_config = SensoConfig.from_env()
        senso_client = SensoClient(senso_config)
        publication = publish_system_of_record(
            client=senso_client,
            raw_snapshot=raw_bundle,
            context_document=normalized_context,
            title_prefix=senso_title_prefix,
        )
        _write_json(receipt_path, publication)
        summary["receipt_path"] = str(receipt_path)
        summary["senso_publication"] = publication

    _append_jsonl(manifest_path, summary)
    return summary
