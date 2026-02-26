from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_INTERNAL_SIGNALS_PATH = Path("data/internal_signals/slack_messages.json")


@dataclass
class InternalSignalSettings:
    signals_path: Path
    default_max_results: int

    @classmethod
    def from_env(cls) -> "InternalSignalSettings":
        signals_path = Path(
            os.getenv("INTERNAL_SIGNALS_PATH", str(DEFAULT_INTERNAL_SIGNALS_PATH))
        ).expanduser()
        default_max_results = int(os.getenv("INTERNAL_SIGNALS_DEFAULT_MAX_RESULTS", "5"))
        return cls(
            signals_path=signals_path,
            default_max_results=max(1, default_max_results),
        )


class InternalSignalSearch:
    def __init__(self, settings: InternalSignalSettings):
        self._settings = settings

    @classmethod
    def from_env(cls) -> "InternalSignalSearch":
        return cls(settings=InternalSignalSettings.from_env())

    def search(
        self,
        *,
        query: str,
        max_results: int | None = None,
        channels: list[str] | None = None,
        hours_back: int | None = None,
    ) -> dict[str, Any]:
        text = str(query or "").strip()
        if not text:
            return {"error": "query is required"}

        entries = self._load_entries()
        if isinstance(entries, dict) and entries.get("error"):
            return entries

        assert isinstance(entries, list)
        terms = self._extract_terms(text)
        channel_filter = {c.strip().lower() for c in (channels or []) if c and c.strip()}
        max_rows = max(1, min(int(max_results or self._settings.default_max_results), 20))

        cutoff: datetime | None = None
        if hours_back is not None:
            try:
                hours = max(1, min(int(hours_back), 24 * 30))
                cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            except (TypeError, ValueError):
                cutoff = None

        scored: list[dict[str, Any]] = []
        for entry in entries:
            channel = str(entry.get("channel", "")).strip()
            channel_l = channel.lower()
            if channel_filter and channel_l not in channel_filter:
                continue

            ts = self._parse_timestamp(entry.get("timestamp"))
            if cutoff is not None and ts is not None and ts < cutoff:
                continue

            score, matched_terms = self._score_entry(entry=entry, terms=terms)
            if score <= 0:
                continue

            scored.append(
                {
                    "message_id": entry.get("id"),
                    "source": entry.get("source", "slack"),
                    "channel": channel,
                    "user": entry.get("user"),
                    "timestamp": entry.get("timestamp"),
                    "text": entry.get("text"),
                    "tags": entry.get("tags") if isinstance(entry.get("tags"), list) else [],
                    "score": score,
                    "matched_terms": matched_terms,
                }
            )

        scored.sort(
            key=lambda item: (
                item.get("score", 0),
                item.get("timestamp") or "",
            ),
            reverse=True,
        )

        return {
            "source": "internal_signal_store",
            "query": text,
            "signals_path": str(self._settings.signals_path.expanduser()),
            "result_count": len(scored[:max_rows]),
            "results": scored[:max_rows],
            "suggested_follow_ups": self._suggest_follow_ups(scored[:max_rows]),
        }

    def _load_entries(self) -> list[dict[str, Any]] | dict[str, Any]:
        path = self._settings.signals_path.expanduser()
        if not path.exists():
            return {
                "error": f"Internal signals file not found: {path}",
                "source": "internal_signal_store",
                "result_count": 0,
                "results": [],
            }

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {
                "error": f"Failed to read internal signals: {exc}",
                "source": "internal_signal_store",
                "result_count": 0,
                "results": [],
            }

        if not isinstance(payload, list):
            return {
                "error": "Internal signals file must be a JSON array.",
                "source": "internal_signal_store",
                "result_count": 0,
                "results": [],
            }

        return [row for row in payload if isinstance(row, dict)]

    @staticmethod
    def _extract_terms(query: str) -> list[str]:
        words = re.findall(r"[a-zA-Z0-9_+-]+", query.lower())
        filtered = [w for w in words if len(w) >= 3]
        seen: set[str] = set()
        unique: list[str] = []
        for term in filtered:
            if term in seen:
                continue
            seen.add(term)
            unique.append(term)
        return unique

    @staticmethod
    def _score_entry(entry: dict[str, Any], terms: list[str]) -> tuple[float, list[str]]:
        text = str(entry.get("text", "")).lower()
        tags = " ".join(str(tag).lower() for tag in entry.get("tags", []) if isinstance(tag, str))
        haystack = f"{text} {tags}"

        matched: list[str] = []
        score = 0.0
        for term in terms:
            if term in haystack:
                matched.append(term)
                score += 1.0
                if term in text:
                    score += 0.4

        # Boost if message appears incident/severity related.
        if any(key in haystack for key in ["incident", "sev", "outage", "checkout", "payment", "bug"]):
            score += 0.5

        return score, matched

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        raw = value.strip()
        if not raw:
            return None
        try:
            if raw.endswith("Z"):
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            return None

    @staticmethod
    def _suggest_follow_ups(results: list[dict[str, Any]]) -> list[str]:
        if not results:
            return [
                "Search for deployment, checkout, payment, or incident keywords.",
                "Broaden time window with hours_back=168.",
            ]

        channels = sorted(
            {
                str(item.get("channel", "")).strip()
                for item in results
                if str(item.get("channel", "")).strip()
            }
        )
        hints: list[str] = []
        if channels:
            hints.append(f"Investigate channels with strongest matches: {', '.join(channels[:3])}.")
        hints.append("Correlate message timestamps with SQL and graph anomalies.")
        return hints
