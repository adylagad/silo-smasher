from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

from .schemas import AGENT_CONTEXT_KIND, AGENT_CONTEXT_SCHEMA_VERSION


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _as_dict(value: Any, fallback: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return fallback or {}


def _as_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _event_status(record: dict[str, Any]) -> str:
    if record.get("returned_at"):
        return "returned"
    if record.get("purchased_at"):
        return "purchased"
    if record.get("added_to_cart_at"):
        return "carted"
    return "unknown"


def normalize_raw_bundle(
    raw_bundle: dict[str, Any], source_metadata: dict[str, Optional[str]]
) -> dict[str, Any]:
    users_raw = _as_list(raw_bundle.get("users"))
    products_raw = _as_list(raw_bundle.get("products"))
    purchases_raw = _as_list(raw_bundle.get("purchases"))

    users = sorted(users_raw, key=lambda x: x.get("id", 0))
    products = sorted(products_raw, key=lambda x: x.get("id", 0))
    purchases = sorted(purchases_raw, key=lambda x: x.get("id", 0))

    users_by_id = {u.get("id"): u for u in users}
    products_by_id = {p.get("id"): p for p in products}

    user_entities: list[dict[str, Any]] = []
    for user in users:
        address = _as_dict(user.get("address"))
        user_entities.append(
            {
                "user_id": user.get("id"),
                "full_name": user.get("name"),
                "email": user.get("email"),
                "age": user.get("age"),
                "gender": user.get("gender"),
                "language": user.get("language"),
                "occupation": user.get("occupation"),
                "address": {
                    "city": address.get("city"),
                    "state": address.get("state"),
                    "province": address.get("province"),
                    "postal_code": address.get("postal_code"),
                    "country_code": address.get("country_code"),
                },
                "created_at": user.get("created_at"),
                "updated_at": user.get("updated_at"),
            }
        )

    product_entities: list[dict[str, Any]] = []
    for product in products:
        product_entities.append(
            {
                "product_id": product.get("id"),
                "make": product.get("make"),
                "model": product.get("model"),
                "year": product.get("year"),
                "price": _to_float(product.get("price")),
                "created_at": product.get("created_at"),
                "updated_at": product.get("updated_at"),
            }
        )

    purchase_events: list[dict[str, Any]] = []
    purchase_counter: Counter[tuple[Any, str]] = Counter()
    country_counter: Counter[str] = Counter()

    purchased_count = 0
    returned_count = 0
    carted_count = 0
    cart_intent_count = 0
    gross_revenue = 0.0
    net_revenue = 0.0

    for purchase in purchases:
        user_id = purchase.get("user_id")
        product_id = purchase.get("product_id")
        user = users_by_id.get(user_id, {})
        product = products_by_id.get(product_id, {})

        status = _event_status(purchase)
        price = _to_float(product.get("price"))

        if purchase.get("added_to_cart_at"):
            cart_intent_count += 1
        if status == "carted":
            carted_count += 1
        if purchase.get("purchased_at"):
            purchased_count += 1
            gross_revenue += price
            purchase_counter[(product_id, f"{product.get('make', '')} {product.get('model', '')}".strip())] += 1
            country_code = _as_dict(user.get("address")).get("country_code")
            if country_code:
                country_counter[str(country_code)] += 1
        if purchase.get("returned_at"):
            returned_count += 1

        if purchase.get("purchased_at") and not purchase.get("returned_at"):
            net_revenue += price

        purchase_events.append(
            {
                "event_id": purchase.get("id"),
                "status": status,
                "user_id": user_id,
                "product_id": product_id,
                "user": {
                    "full_name": user.get("name"),
                    "email": user.get("email"),
                    "country_code": _as_dict(user.get("address")).get("country_code"),
                },
                "product": {
                    "make": product.get("make"),
                    "model": product.get("model"),
                    "price": price,
                },
                "timeline": {
                    "added_to_cart_at": purchase.get("added_to_cart_at"),
                    "purchased_at": purchase.get("purchased_at"),
                    "returned_at": purchase.get("returned_at"),
                    "created_at": purchase.get("created_at"),
                    "updated_at": purchase.get("updated_at"),
                },
            }
        )

    top_products = [
        {
            "product_id": product_id,
            "label": label,
            "purchase_count": count,
        }
        for (product_id, label), count in purchase_counter.most_common(5)
    ]
    country_breakdown = [
        {"country_code": country_code, "purchase_count": count}
        for country_code, count in country_counter.most_common(10)
    ]

    conversion_rate = (purchased_count / cart_intent_count) if cart_intent_count else 0.0
    return_rate = (returned_count / purchased_count) if purchased_count else 0.0

    return {
        "kind": AGENT_CONTEXT_KIND,
        "schema_version": AGENT_CONTEXT_SCHEMA_VERSION,
        "generated_at": _utc_now_iso(),
        "source": {
            "source_name": source_metadata.get("source_name"),
            "workspace_id": source_metadata.get("workspace_id"),
            "connection_id": source_metadata.get("connection_id"),
            "input_sha256": source_metadata.get("input_sha256"),
        },
        "record_counts": {
            "users": len(user_entities),
            "products": len(product_entities),
            "purchases": len(purchase_events),
        },
        "entities": {
            "users": user_entities,
            "products": product_entities,
            "purchase_events": purchase_events,
        },
        "facts": {
            "metrics": {
                "carted_count": carted_count,
                "cart_intent_count": cart_intent_count,
                "purchased_count": purchased_count,
                "returned_count": returned_count,
                "gross_revenue": round(gross_revenue, 2),
                "net_revenue": round(net_revenue, 2),
                "conversion_rate": round(conversion_rate, 6),
                "return_rate": round(return_rate, 6),
            },
            "top_products": top_products,
            "country_purchase_breakdown": country_breakdown,
        },
    }
