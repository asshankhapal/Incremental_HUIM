"""
Transaction and item data models used throughout the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from pydantic import BaseModel, Field


# ── Pydantic schemas (API request / response) ────────────────────────


class TransactionIn(BaseModel):
    """Schema for a single transaction submitted via the ingestion API."""
    items: List[str] = Field(..., min_length=1, description="Item names")
    utilities: List[float] = Field(..., min_length=1, description="Per-item utility values")


class TransactionBatchIn(BaseModel):
    """Schema for a batch of transactions submitted at once."""
    transactions: List[TransactionIn] = Field(..., min_length=1)


class TransactionOut(BaseModel):
    """Schema returned when querying stored transactions."""
    tid: int
    batch_id: int
    items: List[str]
    utilities: List[float]


# ── Internal dataclasses (used by core algorithm) ────────────────────


@dataclass
class Transaction:
    """Internal representation of a single transaction."""
    tid: int
    items: List[str]
    utilities: List[float]
    batch_id: int = 0

    @property
    def transaction_utility(self) -> float:
        """Sum of all item utilities in this transaction (TU)."""
        return sum(self.utilities)

    def remaining_utility(self, after_index: int) -> float:
        """Sum of utilities for items *after* the given index."""
        return sum(self.utilities[after_index + 1:])

    def item_utility_map(self) -> dict[str, float]:
        """Return {item_name: utility} mapping."""
        return dict(zip(self.items, self.utilities))


@dataclass
class TransactionBatch:
    """A batch of transactions that enters/exits the sliding window."""
    batch_id: int
    transactions: List[Transaction] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.transactions)


@dataclass
class UtilityListEntry:
    """
    One entry in an item/pattern's utility list.
    Corresponds to a single transaction containing the item/pattern.
    """
    tid: int
    exact_util: float       # Exact utility of the item/pattern in this txn
    remaining_util: float   # Remaining utility after the item/pattern


@dataclass
class UtilityList:
    """
    Utility list for an item or pattern — the core structure
    used in Phase 4 (DFS mining).
    """
    pattern: tuple[str, ...]                           # e.g. ("A",) or ("A", "B")
    entries: List[UtilityListEntry] = field(default_factory=list)

    @property
    def sum_exact_util(self) -> float:
        return sum(e.exact_util for e in self.entries)

    @property
    def sum_remaining_util(self) -> float:
        return sum(e.remaining_util for e in self.entries)

    @property
    def upper_bound(self) -> float:
        """exact_util + remaining_util — used for pruning."""
        return self.sum_exact_util + self.sum_remaining_util
