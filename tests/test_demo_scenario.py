from __future__ import annotations

import json
from pathlib import Path


def test_uk_shipping_incident_has_partner_dominated_drop() -> None:
    bundle_path = Path(__file__).resolve().parents[1] / "examples" / "uk_shipping_incident.json"
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    users = {int(row["id"]): row for row in payload["users"]}
    product_prices = {int(row["id"]): float(row["price"]) for row in payload["products"]}
    purchases = payload["purchases"]

    cutoff = payload["scenario"]["strike_started_at"]
    country_code = payload["scenario"]["affected_country_code"]
    partner_id = payload["scenario"]["affected_shipping_partner_id"]

    pre_country_revenue = 0.0
    post_country_revenue = 0.0
    pre_partner_revenue = 0.0
    post_partner_revenue = 0.0
    pre_partner_purchased = 0
    post_partner_carted = 0

    for purchase in purchases:
        user = users[int(purchase["user_id"])]
        if user["address"]["country_code"] != country_code:
            continue
        is_post = purchase.get("added_to_cart_at", "") >= cutoff
        price = product_prices[int(purchase["product_id"])]
        if purchase.get("purchased_at"):
            if is_post:
                post_country_revenue += price
            else:
                pre_country_revenue += price
        if purchase.get("shipping_partner_id") == partner_id:
            if purchase.get("purchased_at"):
                if is_post:
                    post_partner_revenue += price
                else:
                    pre_partner_revenue += price
                    pre_partner_purchased += 1
            if is_post and purchase.get("added_to_cart_at") and not purchase.get("purchased_at"):
                post_partner_carted += 1

    country_drop = pre_country_revenue - post_country_revenue
    partner_drop = pre_partner_revenue - post_partner_revenue
    share = partner_drop / country_drop if country_drop > 0 else 0.0

    assert country_drop > 0
    assert partner_drop > 0
    assert share >= 0.8
    assert pre_partner_purchased > 0
    assert post_partner_carted > 0
