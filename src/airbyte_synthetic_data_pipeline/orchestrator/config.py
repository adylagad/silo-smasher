from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class OrchestratorSettings:
    primary_provider: str
    enable_gemini_fallback: bool
    openai_model: str
    gemini_model: str
    gemini_api_key: str | None
    max_tool_rounds: int

    @classmethod
    def from_env(cls) -> "OrchestratorSettings":
        fallback_value = os.getenv("ORCHESTRATOR_ENABLE_GEMINI_FALLBACK", "true").strip().lower()
        enable_gemini_fallback = fallback_value in {"1", "true", "yes", "on"}
        return cls(
            primary_provider=os.getenv("ORCHESTRATOR_PRIMARY_PROVIDER", "openai").strip().lower(),
            enable_gemini_fallback=enable_gemini_fallback,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            gemini_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
            max_tool_rounds=int(os.getenv("OPENAI_MAX_TOOL_ROUNDS", "8")),
        )
