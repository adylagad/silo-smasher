from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class TavilySearchSettings:
    api_key: str | None
    base_url: str
    search_path: str
    timeout_seconds: float
    topic: str
    search_depth: str
    include_answer: str
    fallback_enabled: bool

    @classmethod
    def from_env(cls) -> "TavilySearchSettings":
        fallback_value = os.getenv("TAVILY_FALLBACK_ENABLED", "true").strip().lower()
        search_path = os.getenv("TAVILY_SEARCH_PATH", "/search").strip()
        if not search_path.startswith("/"):
            search_path = f"/{search_path}"
        return cls(
            api_key=os.getenv("TAVILY_API_KEY"),
            base_url=os.getenv("TAVILY_BASE_URL", "https://api.tavily.com").rstrip("/"),
            search_path=search_path,
            timeout_seconds=float(os.getenv("TAVILY_TIMEOUT_SECONDS", "20")),
            topic=os.getenv("TAVILY_TOPIC", "news").strip() or "news",
            search_depth=os.getenv("TAVILY_SEARCH_DEPTH", "basic").strip() or "basic",
            include_answer=os.getenv("TAVILY_INCLUDE_ANSWER", "basic").strip() or "basic",
            fallback_enabled=fallback_value in {"1", "true", "yes", "on"},
        )


class ExternalNewsSearchClient:
    def __init__(self, settings: TavilySearchSettings):
        self._settings = settings

    @classmethod
    def from_env(cls) -> "ExternalNewsSearchClient":
        return cls(settings=TavilySearchSettings.from_env())

    def search_economic_news(
        self,
        *,
        country: str,
        query: str | None = None,
        hours_back: int = 24,
        max_results: int = 5,
    ) -> dict[str, Any]:
        target_country = country.strip()
        if not target_country:
            return {"error": "country is required"}

        resolved_query = (
            query.strip()
            if query and query.strip()
            else f"Major economic news in {target_country} in the last 24 hours"
        )
        clamped_hours = max(1, min(int(hours_back), 168))
        clamped_results = max(1, min(int(max_results), 10))

        if not self._settings.api_key:
            return self._fallback_response(
                country=target_country,
                query=resolved_query,
                hours_back=clamped_hours,
                reason="TAVILY_API_KEY is not configured.",
            )

        url = f"{self._settings.base_url}{self._settings.search_path}"
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {self._settings.api_key}",
        }
        payload: dict[str, Any] = {
            "query": resolved_query,
            "topic": self._settings.topic,
            "search_depth": self._settings.search_depth,
            "max_results": clamped_results,
            "include_answer": self._settings.include_answer,
            "time_range": self._time_range_from_hours(clamped_hours),
        }
        if self._settings.topic == "news":
            payload["days"] = max(1, math.ceil(clamped_hours / 24))

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
                return {"source": "tavily_api", "provider_payload": parsed}
            return self._normalize_response(
                parsed=parsed,
                country=target_country,
                query=resolved_query,
                hours_back=clamped_hours,
            )
        except Exception as exc:
            if self._settings.fallback_enabled:
                return self._fallback_response(
                    country=target_country,
                    query=resolved_query,
                    hours_back=clamped_hours,
                    reason=f"Tavily API call failed: {exc}",
                )
            return {
                "error": "tavily_search_failed",
                "detail": str(exc),
                "country": target_country,
                "query": resolved_query,
                "hours_back": clamped_hours,
            }

    @staticmethod
    def _time_range_from_hours(hours_back: int) -> str:
        if hours_back <= 24:
            return "day"
        if hours_back <= 24 * 7:
            return "week"
        return "month"

    @staticmethod
    def _normalize_response(
        *,
        parsed: dict[str, Any],
        country: str,
        query: str,
        hours_back: int,
    ) -> dict[str, Any]:
        raw_results = parsed.get("results")
        normalized_results: list[dict[str, Any]] = []
        if isinstance(raw_results, list):
            for item in raw_results:
                if not isinstance(item, dict):
                    continue
                normalized_results.append(
                    {
                        "title": item.get("title"),
                        "url": item.get("url"),
                        "content": item.get("content") or item.get("snippet"),
                        "published_date": item.get("published_date"),
                        "score": item.get("score"),
                    }
                )

        answer = parsed.get("answer")
        return {
            "source": "tavily_api",
            "country": country,
            "query": query,
            "hours_back": hours_back,
            "answer": answer if isinstance(answer, str) else None,
            "results": normalized_results,
            "result_count": len(normalized_results),
            "provider_payload": parsed,
        }

    @staticmethod
    def _fallback_response(
        *,
        country: str,
        query: str,
        hours_back: int,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "source": "local_fallback",
            "country": country,
            "query": query,
            "hours_back": hours_back,
            "fallback_reason": reason,
            "message": (
                "External market-news search is unavailable. Set TAVILY_API_KEY to retrieve "
                "live outside-world signals."
            ),
            "suggested_manual_searches": [
                query,
                f"{country} central bank announcement last {hours_back} hours",
                f"{country} currency movement and macro headlines today",
            ],
        }
