from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class OrchestratorSettings:
    openai_model: str
    max_tool_rounds: int

    @classmethod
    def from_env(cls) -> "OrchestratorSettings":
        return cls(
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            max_tool_rounds=int(os.getenv("OPENAI_MAX_TOOL_ROUNDS", "8")),
        )

