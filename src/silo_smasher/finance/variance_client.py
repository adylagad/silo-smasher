from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class RevenueVarianceSettings:
    api_key: str | None
    base_url: str
    variance_path: str
    timeout_seconds: float
    materiality_threshold_pct: float
    fallback_enabled: bool

    @classmethod
    def from_env(cls) -> "RevenueVarianceSettings":
        fallback_value = os.getenv("NUMERIC_FALLBACK_ENABLED", "true").strip().lower()
        return cls(
            api_key=cls._clean_api_key(os.getenv("NUMERIC_API_KEY")),
            base_url=os.getenv("NUMERIC_BASE_URL", "https://api.numeric.io").rstrip("/"),
            variance_path=os.getenv("NUMERIC_VARIANCE_PATH", "/v1/variance/analysis").strip(),
            timeout_seconds=float(os.getenv("NUMERIC_TIMEOUT_SECONDS", "20")),
            materiality_threshold_pct=float(os.getenv("NUMERIC_MATERIALITY_THRESHOLD_PCT", "0.1")),
            fallback_enabled=fallback_value in {"1", "true", "yes", "on"},
        )

    @staticmethod
    def _clean_api_key(value: str | None) -> str | None:
        if not value:
            return None
        cleaned = value.strip()
        if cleaned in {"__MISSING__", "__SET_ME__"}:
            return None
        return cleaned


class RevenueVarianceClient:
    def __init__(self, settings: RevenueVarianceSettings):
        self._settings = settings

    @classmethod
    def from_env(cls) -> "RevenueVarianceClient":
        return cls(settings=RevenueVarianceSettings.from_env())

    def explain_revenue_dip(
        self,
        *,
        current_revenue: float,
        prior_revenue: float,
        period_label: str | None = None,
        region: str | None = None,
        historical_change_pct: float | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        if not self._settings.api_key:
            return self._fallback_explanation(
                current_revenue=current_revenue,
                prior_revenue=prior_revenue,
                period_label=period_label,
                region=region,
                historical_change_pct=historical_change_pct,
                notes=notes,
                source="local_fallback",
                reason="NUMERIC_API_KEY is not configured.",
            )

        endpoint_path = self._settings.variance_path
        if not endpoint_path.startswith("/"):
            endpoint_path = f"/{endpoint_path}"
        url = f"{self._settings.base_url}{endpoint_path}"

        payload = {
            "metric": "revenue",
            "question": "Is this a standard seasonal dip or an accounting anomaly? Provide a CFO-level explanation.",
            "current_value": float(current_revenue),
            "prior_value": float(prior_revenue),
            "period_label": period_label,
            "region": region,
            "historical_change_pct": historical_change_pct,
            "notes": notes,
        }
        headers = {
            "content-type": "application/json",
            "x-api-key": self._settings.api_key,
            "authorization": f"Bearer {self._settings.api_key}",
        }
        try:
            response = requests.post(
                url=url,
                headers=headers,
                json=payload,
                timeout=self._settings.timeout_seconds,
            )
            response.raise_for_status()
            parsed = response.json()
            if isinstance(parsed, dict):
                return self._normalize_provider_payload(parsed)
            return {
                "source": "numeric_api",
                "provider_payload": parsed,
            }
        except Exception as exc:
            if not self._settings.fallback_enabled:
                return {
                    "error": "numeric_variance_request_failed",
                    "detail": str(exc),
                    "url": url,
                }
            return self._fallback_explanation(
                current_revenue=current_revenue,
                prior_revenue=prior_revenue,
                period_label=period_label,
                region=region,
                historical_change_pct=historical_change_pct,
                notes=notes,
                source="local_fallback",
                reason=f"Numeric API call failed: {exc}",
            )

    @staticmethod
    def _normalize_provider_payload(payload: dict[str, Any]) -> dict[str, Any]:
        label_candidates = [
            payload.get("classification"),
            payload.get("label"),
            payload.get("category"),
            payload.get("verdict"),
        ]
        classification = next(
            (str(value) for value in label_candidates if isinstance(value, str) and value.strip()),
            "provider_response",
        )
        confidence = payload.get("confidence")
        explanation_candidates = [
            payload.get("explanation"),
            payload.get("analysis"),
            payload.get("summary"),
            payload.get("message"),
        ]
        explanation = next(
            (str(value) for value in explanation_candidates if isinstance(value, str) and value.strip()),
            "Numeric returned a variance response.",
        )
        return {
            "source": "numeric_api",
            "classification": classification,
            "confidence": float(confidence) if isinstance(confidence, (int, float)) else None,
            "cfo_explanation": explanation,
            "provider_payload": payload,
        }

    def _fallback_explanation(
        self,
        *,
        current_revenue: float,
        prior_revenue: float,
        period_label: str | None,
        region: str | None,
        historical_change_pct: float | None,
        notes: str | None,
        source: str,
        reason: str,
    ) -> dict[str, Any]:
        current = float(current_revenue)
        prior = float(prior_revenue)
        delta_value = current - prior
        delta_pct = self._compute_change_pct(current=current, prior=prior)
        materiality = float(self._settings.materiality_threshold_pct)

        if delta_pct >= 0:
            classification = "no_revenue_dip"
            confidence = 0.86
            cfo_explanation = (
                f"Revenue increased by {delta_pct:.2%}; this is not a dip. "
                "No anomaly signal from local variance heuristic."
            )
        else:
            delta_abs = abs(delta_pct)
            baseline = historical_change_pct
            baseline_gap = abs(delta_pct - baseline) if isinstance(baseline, (int, float)) else None
            appears_seasonal = (
                delta_abs <= materiality
                or (
                    baseline_gap is not None
                    and baseline is not None
                    and delta_pct < 0
                    and abs(baseline) > 0
                    and baseline_gap <= 0.04
                )
            )
            if appears_seasonal:
                classification = "standard_seasonal_dip"
                confidence = 0.68
                cfo_explanation = (
                    f"Revenue declined by {delta_abs:.2%}, which appears within normal seasonal variance "
                    "based on the configured materiality threshold and baseline trend."
                )
            else:
                classification = "accounting_anomaly_likely"
                confidence = 0.77
                cfo_explanation = (
                    f"Revenue declined by {delta_abs:.2%}, which exceeds normal materiality thresholds "
                    "and likely indicates an accounting or operational anomaly requiring investigation."
                )

        return {
            "source": source,
            "classification": classification,
            "confidence": confidence,
            "period_label": period_label,
            "region": region,
            "current_revenue": current,
            "prior_revenue": prior,
            "delta_value": round(delta_value, 2),
            "delta_pct": round(delta_pct, 6),
            "historical_change_pct": historical_change_pct,
            "cfo_explanation": cfo_explanation,
            "notes": notes,
            "fallback_reason": reason,
        }

    @staticmethod
    def _compute_change_pct(*, current: float, prior: float) -> float:
        if prior == 0:
            if current == 0:
                return 0.0
            return 1.0 if current > 0 else -1.0
        return (current - prior) / abs(prior)
