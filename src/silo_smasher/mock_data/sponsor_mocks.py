from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any


def mock_data_enabled() -> bool:
    raw = os.getenv("SPONSOR_MOCK_DATA_ENABLED", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def mock_revenue_variance(
    *,
    current_revenue: float,
    prior_revenue: float,
    period_label: str | None,
    region: str | None,
    historical_change_pct: float | None,
    reason: str,
) -> dict[str, Any]:
    prior = float(prior_revenue)
    current = float(current_revenue)
    delta_value = current - prior
    delta_pct = ((current - prior) / abs(prior)) if prior else (1.0 if current > 0 else 0.0)

    if delta_pct >= 0:
        classification = "no_revenue_dip"
        confidence = 0.91
        summary = "No decline detected; the structured trend is stable or improving."
    elif abs(delta_pct) <= 0.08:
        classification = "standard_seasonal_dip"
        confidence = 0.74
        summary = "Dip is within a normal seasonal band based on expected range."
    else:
        classification = "operational_anomaly_likely"
        confidence = 0.83
        summary = "Drop magnitude exceeds seasonal band and points to an operational issue."

    return {
        "source": "mock_data",
        "classification": classification,
        "confidence": confidence,
        "period_label": period_label,
        "region": region,
        "current_revenue": current,
        "prior_revenue": prior,
        "delta_value": round(delta_value, 2),
        "delta_pct": round(delta_pct, 6),
        "historical_change_pct": historical_change_pct,
        "cfo_explanation": (
            f"{summary} Current period is {delta_pct:.2%} versus prior period. "
            "Recommendation: verify region-level shipment throughput and payment failure logs."
        ),
        "mock_reason": reason,
    }


def mock_external_news(
    *,
    country: str,
    query: str,
    hours_back: int,
    reason: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    items = [
        {
            "title": f"Logistics disruption reported across {country}",
            "url": "https://example.com/economic/logistics-disruption",
            "content": (
                "Transport and customs throughput slowed in key corridors, increasing delivery latency."
            ),
            "published_date": (now - timedelta(hours=6)).isoformat().replace("+00:00", "Z"),
            "score": 0.86,
        },
        {
            "title": f"Consumer demand softens in {country} retail index",
            "url": "https://example.com/economic/retail-index",
            "content": (
                "Latest high-frequency demand indicators show weaker conversion in online channels."
            ),
            "published_date": (now - timedelta(hours=11)).isoformat().replace("+00:00", "Z"),
            "score": 0.79,
        },
    ]
    return {
        "source": "mock_data",
        "country": country,
        "query": query,
        "hours_back": hours_back,
        "answer": (
            f"Mock market signal: the last {hours_back} hours show logistics and demand headwinds in {country}."
        ),
        "results": items,
        "result_count": len(items),
        "mock_reason": reason,
    }


def mock_portal_report(
    *,
    portal_url: str,
    report_hint: str | None,
    reason: str,
) -> dict[str, Any]:
    published_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "source": "mock_data",
        "status": "mock_report_returned",
        "portal_url": portal_url,
        "report_hint": report_hint,
        "report": {
            "title": "Weekly Operations Brief",
            "published_at": published_at,
            "pdf_url": "https://example.com/internal/weekly-operations-brief.pdf",
            "summary": (
                "Regional shipment delays and elevated support ticket volume correlated with conversion softness."
            ),
            "kpis": {
                "delivery_delay_pct": 12.4,
                "checkout_failure_rate_pct": 3.8,
                "support_ticket_change_pct": 19.2,
            },
            "evidence_snippets": [
                "Carrier SLA misses increased in two key regions during the same interval as revenue decline.",
                "Checkout retries and payment declines increased after a service rollout.",
            ],
        },
        "mock_reason": reason,
    }


def mock_voice_analysis(
    *,
    utterance: str,
    reason: str,
    stress_threshold: float,
) -> dict[str, Any]:
    normalized = (utterance or "").strip()
    lowered = normalized.lower()
    urgent_hits = len(re.findall(r"\b(urgent|asap|now|stressed|panic|frustrated|worried)\b", lowered))
    stress_score = min(1.0, 0.35 + urgent_hits * 0.18) if normalized else 0.0

    if "summary" in lowered or stress_score >= stress_threshold:
        mode = "summary_mode"
        intent = "summary_request"
        emotion = "stressed" if stress_score >= stress_threshold else "focused"
    else:
        mode = "deep_dive_mode"
        intent = "diagnostic_request"
        emotion = "neutral"

    return {
        "source": "mock_data",
        "transcript": normalized,
        "intent": intent,
        "emotion": emotion,
        "stress_score": round(stress_score, 4),
        "recommended_response_mode": mode,
        "policy_reason": (
            "Mock detector prioritized concise output due to stress/urgency cues."
            if mode == "summary_mode"
            else "Mock detector allows deep-dive analysis."
        ),
        "mock_reason": reason,
    }


def mock_senso_content(*, content_id: str, reason: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "source": "mock_data",
        "id": content_id,
        "title": "Verified System Record Snapshot",
        "summary": "Mock Senso document representing a verified context artifact.",
        "processing_status": "completed",
        "created_at": now,
        "updated_at": now,
        "text": (
            "Ground-truth snapshot indicates a localized conversion drop with coincident ticket volume increase."
        ),
        "mock_reason": reason,
    }
