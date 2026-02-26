from __future__ import annotations

import json
from pathlib import Path

from silo_smasher.context.normalize import normalize_raw_bundle
from silo_smasher.context.schemas import AGENT_CONTEXT_KIND, AGENT_CONTEXT_SCHEMA_VERSION


def test_normalize_raw_bundle_metrics_and_schema() -> None:
    bundle_path = Path(__file__).resolve().parents[1] / "examples" / "synthetic_raw_bundle.json"
    raw_bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

    normalized = normalize_raw_bundle(
        raw_bundle=raw_bundle,
        source_metadata={
            "source_name": "test_source",
            "workspace_id": "ws_test",
            "connection_id": "conn_test",
            "input_sha256": "abc123",
        },
    )

    assert normalized["kind"] == AGENT_CONTEXT_KIND
    assert normalized["schema_version"] == AGENT_CONTEXT_SCHEMA_VERSION

    entities = normalized["entities"]
    metrics = normalized["facts"]["metrics"]

    users = raw_bundle["users"]
    products = raw_bundle["products"]
    purchases = raw_bundle["purchases"]
    products_by_id = {row["id"]: row for row in products}

    purchased_count = sum(1 for row in purchases if row.get("purchased_at"))
    returned_count = sum(1 for row in purchases if row.get("returned_at"))
    cart_intent_count = sum(1 for row in purchases if row.get("added_to_cart_at"))
    carted_count = sum(
        1
        for row in purchases
        if row.get("added_to_cart_at") and not row.get("purchased_at") and not row.get("returned_at")
    )

    gross_revenue = sum(
        float(products_by_id.get(row.get("product_id"), {}).get("price", 0.0) or 0.0)
        for row in purchases
        if row.get("purchased_at")
    )
    net_revenue = sum(
        float(products_by_id.get(row.get("product_id"), {}).get("price", 0.0) or 0.0)
        for row in purchases
        if row.get("purchased_at") and not row.get("returned_at")
    )
    conversion_rate = (purchased_count / cart_intent_count) if cart_intent_count else 0.0
    return_rate = (returned_count / purchased_count) if purchased_count else 0.0

    assert len(entities["users"]) == len(users)
    assert len(entities["products"]) == len(products)
    assert len(entities["purchase_events"]) == len(purchases)

    assert metrics["purchased_count"] == purchased_count
    assert metrics["returned_count"] == returned_count
    assert metrics["cart_intent_count"] == cart_intent_count
    assert metrics["carted_count"] == carted_count
    assert metrics["gross_revenue"] == round(gross_revenue, 2)
    assert metrics["net_revenue"] == round(net_revenue, 2)
    assert metrics["conversion_rate"] == round(conversion_rate, 6)
    assert metrics["return_rate"] == round(return_rate, 6)
