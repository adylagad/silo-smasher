from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from silo_smasher.finance import RevenueVarianceClient
from silo_smasher.internal_signals import InternalSignalSearch
from silo_smasher.market_signals import ExternalNewsSearchClient
from silo_smasher.pipeline import run_ground_truth_pipeline


@dataclass
class ScenarioMetrics:
    cutoff_timestamp: str
    affected_country_code: str
    affected_shipping_partner_id: str
    affected_shipping_partner_name: str
    pre_country_revenue: float
    post_country_revenue: float
    country_revenue_drop: float
    pre_partner_revenue: float
    post_partner_revenue: float
    partner_revenue_drop: float
    partner_drop_share_of_country_drop: float
    partner_status_counts_pre: dict[str, int]
    partner_status_counts_post: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cutoff_timestamp": self.cutoff_timestamp,
            "affected_country_code": self.affected_country_code,
            "affected_shipping_partner_id": self.affected_shipping_partner_id,
            "affected_shipping_partner_name": self.affected_shipping_partner_name,
            "pre_country_revenue": round(self.pre_country_revenue, 2),
            "post_country_revenue": round(self.post_country_revenue, 2),
            "country_revenue_drop": round(self.country_revenue_drop, 2),
            "pre_partner_revenue": round(self.pre_partner_revenue, 2),
            "post_partner_revenue": round(self.post_partner_revenue, 2),
            "partner_revenue_drop": round(self.partner_revenue_drop, 2),
            "partner_drop_share_of_country_drop": round(
                self.partner_drop_share_of_country_drop, 6
            ),
            "partner_status_counts_pre": self.partner_status_counts_pre,
            "partner_status_counts_post": self.partner_status_counts_post,
        }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic UK shipping-incident demo scenario end-to-end."
    )
    parser.add_argument(
        "--bundle",
        default="examples/uk_shipping_incident.json",
        help="Path to the tailored synthetic bundle.",
    )
    parser.add_argument(
        "--output-root",
        default="demo/output/system_of_record",
        help="System-of-record output root for raw/context/manifest artifacts.",
    )
    parser.add_argument(
        "--output-file",
        default="demo/output/latest_demo_brief.json",
        help="Where to write the demo brief JSON artifact.",
    )
    parser.add_argument(
        "--question",
        default=None,
        help="Optional override for the diagnostic question.",
    )
    parser.add_argument(
        "--publish-to-senso",
        action="store_true",
        help="Publish the generated context to Senso.",
    )
    parser.add_argument(
        "--allow-live-model",
        action="store_true",
        help=(
            "Allow live OpenAI/Gemini/Numeric/Tavily calls. By default, provider keys are "
            "temporarily masked so output stays deterministic via local fallback/mock mode."
        ),
    )
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at {path}")
    return payload


def _event_status(purchase: dict[str, Any]) -> str:
    if purchase.get("returned_at"):
        return "returned"
    if purchase.get("purchased_at"):
        return "purchased"
    if purchase.get("added_to_cart_at"):
        return "carted"
    return "unknown"


def _compute_metrics(bundle: dict[str, Any], scenario: dict[str, Any]) -> ScenarioMetrics:
    users = {
        int(row.get("id")): row
        for row in bundle.get("users", [])
        if isinstance(row, dict) and row.get("id") is not None
    }
    products = {
        int(row.get("id")): float(row.get("price", 0.0) or 0.0)
        for row in bundle.get("products", [])
        if isinstance(row, dict) and row.get("id") is not None
    }
    purchases = [
        row for row in bundle.get("purchases", []) if isinstance(row, dict)
    ]

    cutoff = str(scenario.get("strike_started_at", "")).strip()
    country_code = str(scenario.get("affected_country_code", "")).strip()
    partner_id = str(scenario.get("affected_shipping_partner_id", "")).strip()
    partner_name = str(
        scenario.get("affected_shipping_partner_name", partner_id)
    ).strip() or partner_id

    if not cutoff or not country_code or not partner_id:
        raise RuntimeError("Scenario metadata requires strike_started_at/country/partner.")

    pre_country_revenue = 0.0
    post_country_revenue = 0.0
    pre_partner_revenue = 0.0
    post_partner_revenue = 0.0
    partner_pre_status = Counter()
    partner_post_status = Counter()

    for purchase in purchases:
        user_id = purchase.get("user_id")
        if user_id is None:
            continue
        user = users.get(int(user_id))
        if not isinstance(user, dict):
            continue
        user_country = (
            user.get("address", {}).get("country_code")
            if isinstance(user.get("address"), dict)
            else None
        )
        if str(user_country or "").strip() != country_code:
            continue

        added_to_cart_at = str(purchase.get("added_to_cart_at") or "").strip()
        period = "post" if added_to_cart_at and added_to_cart_at >= cutoff else "pre"
        status = _event_status(purchase)
        shipping_partner_id = str(purchase.get("shipping_partner_id") or "").strip()
        product_id = purchase.get("product_id")
        price = products.get(int(product_id), 0.0) if product_id is not None else 0.0

        if purchase.get("purchased_at"):
            if period == "pre":
                pre_country_revenue += price
            else:
                post_country_revenue += price

            if shipping_partner_id == partner_id:
                if period == "pre":
                    pre_partner_revenue += price
                else:
                    post_partner_revenue += price

        if shipping_partner_id == partner_id:
            if period == "pre":
                partner_pre_status[status] += 1
            else:
                partner_post_status[status] += 1

    country_drop = pre_country_revenue - post_country_revenue
    partner_drop = pre_partner_revenue - post_partner_revenue
    share = (partner_drop / country_drop) if country_drop > 0 else 0.0

    return ScenarioMetrics(
        cutoff_timestamp=cutoff,
        affected_country_code=country_code,
        affected_shipping_partner_id=partner_id,
        affected_shipping_partner_name=partner_name,
        pre_country_revenue=pre_country_revenue,
        post_country_revenue=post_country_revenue,
        country_revenue_drop=country_drop,
        pre_partner_revenue=pre_partner_revenue,
        post_partner_revenue=post_partner_revenue,
        partner_revenue_drop=partner_drop,
        partner_drop_share_of_country_drop=share,
        partner_status_counts_pre=dict(partner_pre_status),
        partner_status_counts_post=dict(partner_post_status),
    )


def _compose_extra_context(
    *,
    scenario: dict[str, Any],
    metrics: ScenarioMetrics,
) -> str:
    payload = {
        "scenario": {
            "name": scenario.get("name"),
            "expected_story": scenario.get("expected_story"),
            "affected_shipping_partner_name": metrics.affected_shipping_partner_name,
            "affected_shipping_partner_id": metrics.affected_shipping_partner_id,
            "strike_started_at": metrics.cutoff_timestamp,
            "affected_country_code": metrics.affected_country_code,
        },
        "deterministic_evidence": metrics.to_dict(),
    }
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True)


def _run_orchestrator(
    *,
    question: str,
    extra_context: str,
    allow_live_model: bool,
) -> dict[str, Any]:
    try:
        from silo_smasher.orchestrator import DiagnosticOrchestrator, OrchestratorSettings
    except Exception as exc:
        return {
            "error": "orchestrator_runtime_unavailable",
            "detail": str(exc),
        }

    key_names = ["OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"]
    local_demo_key = "ORCHESTRATOR_ENABLE_LOCAL_DEMO_FALLBACK"
    previous_values: dict[str, str | None] = {}
    if not allow_live_model:
        for key_name in key_names:
            previous_values[key_name] = os.environ.get(key_name)
            if key_name in os.environ:
                del os.environ[key_name]
        previous_values[local_demo_key] = os.environ.get(local_demo_key)
        os.environ[local_demo_key] = "true"

    try:
        orchestrator = DiagnosticOrchestrator(OrchestratorSettings.from_env())
        return orchestrator.run(question=question, extra_context=extra_context)
    finally:
        if not allow_live_model:
            for key_name in key_names:
                previous = previous_values.get(key_name)
                if previous is None:
                    os.environ.pop(key_name, None)
                else:
                    os.environ[key_name] = previous
            local_demo_previous = previous_values.get(local_demo_key)
            if local_demo_previous is None:
                os.environ.pop(local_demo_key, None)
            else:
                os.environ[local_demo_key] = local_demo_previous


def main() -> None:
    load_dotenv()
    logging.getLogger("neo4j").setLevel(logging.CRITICAL)
    args = _parse_args()

    bundle_path = (PROJECT_ROOT / args.bundle).expanduser().resolve()
    output_root = (PROJECT_ROOT / args.output_root).expanduser().resolve()
    output_file = (PROJECT_ROOT / args.output_file).expanduser().resolve()

    payload = _load_json(bundle_path)
    scenario = payload.get("scenario")
    if not isinstance(scenario, dict):
        raise RuntimeError("Tailored bundle must include top-level scenario metadata.")

    question = str(args.question or scenario.get("default_question") or "").strip()
    if not question:
        raise RuntimeError("No demo question provided and scenario.default_question missing.")

    metrics = _compute_metrics(bundle=payload, scenario=scenario)

    signals_path_raw = str(scenario.get("internal_signals_path", "")).strip()
    signals_path = (
        (PROJECT_ROOT / signals_path_raw).resolve()
        if signals_path_raw
        else (PROJECT_ROOT / "data/internal_signals/slack_messages.json").resolve()
    )
    os.environ["INTERNAL_SIGNALS_PATH"] = str(signals_path)

    pipeline_summary = run_ground_truth_pipeline(
        input_path=bundle_path,
        output_root=output_root,
        source_name="uk_shipping_incident_demo",
        workspace_id=None,
        connection_id=None,
        publish_to_senso=bool(args.publish_to_senso),
        senso_title_prefix="UK Shipping Incident Demo",
    )

    deterministic_keys = [
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "NUMERIC_API_KEY",
        "TAVILY_API_KEY",
    ]
    previous_env: dict[str, str | None] = {}
    if not args.allow_live_model:
        for key_name in deterministic_keys:
            previous_env[key_name] = os.environ.get(key_name)
            os.environ.pop(key_name, None)
        previous_env["SPONSOR_MOCK_DATA_ENABLED"] = os.environ.get("SPONSOR_MOCK_DATA_ENABLED")
        os.environ["SPONSOR_MOCK_DATA_ENABLED"] = "true"

    try:
        internal_search = InternalSignalSearch.from_env()
        internal_signals = internal_search.search(
            query=(
                f"{metrics.affected_country_code} postal strike checkout incident "
                f"{metrics.affected_shipping_partner_id}"
            ),
            hours_back=72,
            max_results=5,
        )

        variance_client = RevenueVarianceClient.from_env()
        variance = variance_client.explain_revenue_dip(
            current_revenue=metrics.post_country_revenue,
            prior_revenue=metrics.pre_country_revenue,
            period_label="Post-strike vs pre-strike sample window",
            region=metrics.affected_country_code,
            historical_change_pct=-0.04,
            notes=(
                "Deterministic scripted demo scenario for UK shipping incident."
            ),
        )

        news_client = ExternalNewsSearchClient.from_env()
        news = news_client.search_economic_news(
            country=metrics.affected_country_code,
            query=(
                f"Major logistics and postal news in {metrics.affected_country_code} in the last 24 hours"
            ),
            hours_back=24,
            max_results=3,
        )

        extra_context = _compose_extra_context(
            scenario=scenario,
            metrics=metrics,
        )
        orchestrator_output = _run_orchestrator(
            question=question,
            extra_context=extra_context,
            allow_live_model=bool(args.allow_live_model),
        )
    finally:
        if not args.allow_live_model:
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

    share_pct = metrics.partner_drop_share_of_country_drop * 100.0
    top_internal = ""
    if isinstance(internal_signals, dict):
        results = internal_signals.get("results")
        if isinstance(results, list) and results and isinstance(results[0], dict):
            top_internal = str(results[0].get("text") or "").strip()

    top_news = ""
    if isinstance(news, dict):
        results = news.get("results")
        if isinstance(results, list) and results and isinstance(results[0], dict):
            top_news = str(results[0].get("title") or "").strip()

    confidence = 0.93 if share_pct >= 80 else 0.74
    executive_summary = (
        f"{metrics.affected_shipping_partner_name} ({metrics.affected_shipping_partner_id}) "
        f"accounts for {share_pct:.1f}% of the UK revenue drop after "
        f"{metrics.cutoff_timestamp}. This supports the strike-driven root-cause hypothesis."
    )

    demo_report = {
        "question": question,
        "scenario": scenario,
        "deterministic_evidence": metrics.to_dict(),
        "executive_summary": executive_summary,
        "confidence_overall": confidence,
        "pipeline_summary": pipeline_summary,
        "tool_outputs": {
            "internal_signals": internal_signals,
            "variance": variance,
            "external_news": news,
            "orchestrator": orchestrator_output,
        },
        "recommended_actions": [
            "Reroute UK orders away from affected carrier until SLA stabilizes.",
            "Keep checkout mitigation active for UK shipping-selector flow.",
            "Monitor UK conversion and purchased revenue every hour until trend recovers.",
        ],
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(demo_report, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    print("Deterministic Demo Brief")
    print("========================")
    print(f"Question: {question}")
    print(
        "Root Cause: "
        f"{metrics.affected_shipping_partner_name} drives {share_pct:.1f}% of UK drop."
    )
    print(
        "Revenue: "
        f"UK pre={metrics.pre_country_revenue:.2f}, "
        f"post={metrics.post_country_revenue:.2f}, "
        f"drop={metrics.country_revenue_drop:.2f}"
    )
    print(
        "Partner: "
        f"pre={metrics.pre_partner_revenue:.2f}, "
        f"post={metrics.post_partner_revenue:.2f}, "
        f"drop={metrics.partner_revenue_drop:.2f}"
    )
    print(
        "Status Shift: "
        f"pre={metrics.partner_status_counts_pre}, "
        f"post={metrics.partner_status_counts_post}"
    )
    if top_internal:
        print(f"Top Internal Signal: {top_internal}")
    if top_news:
        print(f"Top External Signal: {top_news}")
    print(f"Output File: {output_file}")


if __name__ == "__main__":
    main()
