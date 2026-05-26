from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AISearchConnectionConfig:
    provider: str
    base_url: str
    baseline_index: str
    candidate_index: str
