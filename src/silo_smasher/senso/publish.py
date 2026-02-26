from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .client import SensoClient


def _now_suffix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def publish_system_of_record(
    client: SensoClient,
    raw_snapshot: dict[str, Any],
    context_document: dict[str, Any],
    title_prefix: str,
) -> dict[str, Any]:
    suffix = _now_suffix()
    raw_text = _canonical_json(raw_snapshot)
    context_text = _canonical_json(context_document)

    raw_title = f"{title_prefix} Raw Snapshot {suffix}"
    context_title = f"{title_prefix} Agent Context {suffix}"

    raw_created = client.create_raw_content(
        title=raw_title,
        summary="Raw source snapshot before normalization.",
        text=raw_text,
    )
    raw_content_id = str(raw_created["id"])
    raw_detail = client.wait_for_completed(raw_content_id)

    context_created = client.create_raw_content(
        title=context_title,
        summary="Normalized agent-ready context used as system of record.",
        text=context_text,
    )
    context_content_id = str(context_created["id"])
    context_detail = client.wait_for_completed(context_content_id)

    verified_context_hash = _sha256_text(str(context_detail.get("text", "")))
    local_context_hash = _sha256_text(context_text)
    if verified_context_hash != local_context_hash:
        raise RuntimeError(
            "Senso returned context text that does not match the locally produced JSON."
        )

    return {
        "published_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "raw_content": {
            "id": raw_content_id,
            "title": raw_detail.get("title"),
            "processing_status": raw_detail.get("processing_status"),
            "text_sha256": _sha256_text(str(raw_detail.get("text", ""))),
        },
        "context_content": {
            "id": context_content_id,
            "title": context_detail.get("title"),
            "processing_status": context_detail.get("processing_status"),
            "text_sha256": verified_context_hash,
        },
        "verification": {
            "local_context_sha256": local_context_hash,
            "senso_context_sha256": verified_context_hash,
            "is_match": True,
        },
    }

