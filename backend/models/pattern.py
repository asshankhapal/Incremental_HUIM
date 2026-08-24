"""
Pattern and tracker entry models for Phase 3 (HDkT) and Phase 5 (Validation).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from pydantic import BaseModel


# ── Internal dataclass ───────────────────────────────────────────────


@dataclass
class TrackerEntry:
    """
    One row in the Phase 5 historical HashMap.
    Tracks lifetime statistics for a single discovered pattern.
    """
    pattern_key: str          # Canonical string like "A,B,C"
    total_util: float = 0.0
    count: int = 0
    avg_util: float = 0.0
    last_seen_batch: int = 0

    def update(self, util: float, current_batch: int) -> None:
        """Update entry with a new observation."""
        self.total_util += util
        self.count += 1
        self.avg_util = self.total_util / self.count
        self.last_seen_batch = current_batch

    def decay(self, factor: float) -> None:
        """Apply decay to an unseen pattern."""
        self.total_util *= factor
        if self.count > 0:
            self.avg_util = self.total_util / self.count


@dataclass
class PatternResult:
    """A single high-utility itemset discovered by Phase 4."""
    pattern: tuple[str, ...]
    exact_utility: float

    @property
    def pattern_key(self) -> str:
        return ",".join(self.pattern)


# ── Pydantic schemas (API response) ─────────────────────────────────


class TrackerEntryOut(BaseModel):
    """Schema for returning a pattern tracker entry."""
    pattern_key: str
    total_util: float
    count: int
    avg_util: float
    last_seen_batch: int


class TopKResultOut(BaseModel):
    """Schema for returning top-k results."""
    rank: int
    pattern_key: str
    avg_util: float
    count: int
    last_seen_batch: int


class PipelineStatusOut(BaseModel):
    """Schema for pipeline run status."""
    run_id: int
    started_at: str
    finished_at: str | None = None
    status: str
    details: dict | None = None
