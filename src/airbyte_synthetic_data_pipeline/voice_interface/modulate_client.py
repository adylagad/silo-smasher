from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

import requests


STRESS_TERMS = {
    "stressed",
    "stress",
    "urgent",
    "asap",
    "panic",
    "panicking",
    "frustrated",
    "worried",
    "anxious",
    "blocked",
    "angry",
}

SUMMARY_INTENT_TERMS = {
    "summary",
    "quickly",
    "brief",
    "tl;dr",
    "high-level",
}

DEEP_DIVE_INTENT_TERMS = {
    "deep dive",
    "details",
    "root cause",
    "why exactly",
    "full analysis",
    "breakdown",
}


@dataclass
class VoiceCommandSettings:
    api_key: str | None
    base_url: str
    analyze_path: str
    timeout_seconds: float
    stress_threshold: float
    fallback_enabled: bool

    @classmethod
    def from_env(cls) -> "VoiceCommandSettings":
        fallback_value = os.getenv("MODULATE_FALLBACK_ENABLED", "true").strip().lower()
        analyze_path = os.getenv("MODULATE_ANALYZE_PATH", "/v1/velma/analyze").strip()
        if not analyze_path.startswith("/"):
            analyze_path = f"/{analyze_path}"
        threshold = float(os.getenv("MODULATE_STRESS_THRESHOLD", "0.6"))
        threshold = max(0.0, min(threshold, 1.0))
        return cls(
            api_key=os.getenv("MODULATE_API_KEY"),
            base_url=os.getenv("MODULATE_BASE_URL", "https://api.modulate.ai").rstrip("/"),
            analyze_path=analyze_path,
            timeout_seconds=float(os.getenv("MODULATE_TIMEOUT_SECONDS", "20")),
            stress_threshold=threshold,
            fallback_enabled=fallback_value in {"1", "true", "yes", "on"},
        )


class VoiceCommandAnalyzer:
    def __init__(self, settings: VoiceCommandSettings):
        self._settings = settings

    @classmethod
    def from_env(cls) -> "VoiceCommandAnalyzer":
        return cls(settings=VoiceCommandSettings.from_env())

    def analyze_command(
        self,
        *,
        utterance: str,
        audio_url: str | None = None,
        context: str | None = None,
    ) -> dict[str, Any]:
        text = (utterance or "").strip()
        if not text and not (audio_url and audio_url.strip()):
            return {"error": "utterance or audio_url is required"}

        if not self._settings.api_key:
            return self._fallback_analysis(
                utterance=text,
                source="local_fallback",
                reason="MODULATE_API_KEY is not configured.",
            )

        url = f"{self._settings.base_url}{self._settings.analyze_path}"
        headers = {
            "content-type": "application/json",
            "x-api-key": self._settings.api_key,
            "authorization": f"Bearer {self._settings.api_key}",
        }
        payload: dict[str, Any] = {
            "engine": "velma-2.0",
            "utterance": text,
            "audio_url": audio_url,
            "context": context,
            "tasks": ["transcription", "intent", "emotion"],
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
            if not isinstance(parsed, dict):
                return {"source": "modulate_api", "provider_payload": parsed}
            return self._normalize_provider_response(parsed, utterance=text)
        except Exception as exc:
            if self._settings.fallback_enabled:
                return self._fallback_analysis(
                    utterance=text,
                    source="local_fallback",
                    reason=f"Modulate API call failed: {exc}",
                )
            return {
                "error": "modulate_analysis_failed",
                "detail": str(exc),
            }

    def _normalize_provider_response(self, payload: dict[str, Any], utterance: str) -> dict[str, Any]:
        transcript = self._pick_text(payload, ["transcript", "text", "utterance"]) or utterance
        intent = self._pick_text(payload, ["intent", "intent_label", "detected_intent"]) or "unknown"
        emotion = self._pick_text(payload, ["emotion", "emotion_label", "detected_emotion"]) or "neutral"
        stress_score = self._pick_numeric(payload, ["stress_score", "stress", "emotion_intensity"])
        if stress_score is None:
            stress_score = 0.0

        mode = self._choose_response_mode(
            intent=intent.lower(),
            emotion=emotion.lower(),
            stress_score=float(stress_score),
        )
        return {
            "source": "modulate_api",
            "transcript": transcript,
            "intent": intent,
            "emotion": emotion,
            "stress_score": float(stress_score),
            "recommended_response_mode": mode,
            "policy_reason": (
                "User appears stressed; prioritize summary mode."
                if mode == "summary_mode"
                else "Stress below threshold; deep-dive mode allowed."
            ),
            "provider_payload": payload,
        }

    def _fallback_analysis(self, *, utterance: str, source: str, reason: str) -> dict[str, Any]:
        lowered = utterance.lower()
        tokens = set(re.findall(r"[a-zA-Z0-9_+-]+", lowered))

        stress_hits = len(tokens.intersection(STRESS_TERMS))
        punctuation_signal = min(0.2, utterance.count("!") * 0.05)
        uppercase_signal = 0.15 if utterance.isupper() and utterance else 0.0
        stress_score = min(1.0, stress_hits * 0.2 + punctuation_signal + uppercase_signal)
        if stress_hits > 0 and stress_score < self._settings.stress_threshold:
            stress_score = self._settings.stress_threshold

        if any(term in lowered for term in DEEP_DIVE_INTENT_TERMS):
            intent = "deep_dive_request"
        elif any(term in lowered for term in SUMMARY_INTENT_TERMS):
            intent = "summary_request"
        elif "why" in tokens or "reason" in tokens:
            intent = "root_cause_request"
        else:
            intent = "general_query"

        emotion = "stressed" if stress_score >= self._settings.stress_threshold else "neutral"
        mode = self._choose_response_mode(intent=intent, emotion=emotion, stress_score=stress_score)
        return {
            "source": source,
            "transcript": utterance,
            "intent": intent,
            "emotion": emotion,
            "stress_score": round(stress_score, 4),
            "recommended_response_mode": mode,
            "policy_reason": (
                "Stress detected by fallback heuristic; prioritize summary mode."
                if mode == "summary_mode"
                else "No high stress detected by fallback heuristic."
            ),
            "fallback_reason": reason,
        }

    def _choose_response_mode(self, *, intent: str, emotion: str, stress_score: float) -> str:
        stressed = (
            stress_score >= self._settings.stress_threshold
            or emotion in {"stressed", "anxious", "angry", "frustrated", "panic"}
        )
        if stressed:
            return "summary_mode"
        if intent in {"summary_request"}:
            return "summary_mode"
        return "deep_dive_mode"

    @staticmethod
    def _pick_text(payload: dict[str, Any], keys: list[str]) -> str | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _pick_numeric(payload: dict[str, Any], keys: list[str]) -> float | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, (int, float)):
                return float(value)
        return None
