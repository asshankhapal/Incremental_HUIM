"""
Phase 3 — HDkT (Historical Decay-k Threshold)

Step 1: Active Leaderboard Extraction & Stale Filtering
    From the Phase 5 HashMap, filter out stale patterns (current_batch -
    last_seen_batch > stale_limit).  Select top-k by avg_util.

Step 2: Decay-Smoothed Delta Projection  (O(k))
    For each pattern P in the watchlist:
        Projected_U(P) = P.avg_util + U(P, batch_new) - U(P, batch_old)

Step 3: Instant Threshold Calculation  (O(1))
    current_min_util = min(Projected_U(P1), ..., Projected_U(Pk))
"""

from __future__ import annotations

import json
from typing import Optional

from config import config
from database import get_db
from models.transaction import TransactionBatch


class HDkTCalculator:
    """Computes the dynamic minimum-utility threshold for Phase 4 pruning."""

    def compute_threshold(
        self,
        current_batch_id: int,
        batch_new: Optional[TransactionBatch],
        batch_old: Optional[TransactionBatch],
    ) -> float:
        """
        Run all three HDkT steps and return the current_min_util.

        Returns 0.0 when there are fewer than k active patterns
        (no pruning is possible yet).
        """
        # Step 1 — Active leaderboard extraction
        watchlist = self._extract_watchlist(current_batch_id)

        if len(watchlist) < config.top_k:
            return 0.0

        # Step 2 — Decay-smoothed delta projection
        projected: list[float] = []
        for entry in watchlist:
            pattern_items = entry["pattern_key"].split(",")
            delta_new = (
                self._pattern_utility_in_batch(pattern_items, batch_new)
                if batch_new
                else 0.0
            )
            delta_old = (
                self._pattern_utility_in_batch(pattern_items, batch_old)
                if batch_old
                else 0.0
            )
            proj = entry["avg_util"] + delta_new - delta_old
            projected.append(proj)

        # Step 3 — Instant threshold
        current_min_util = min(projected) if projected else 0.0
        return max(current_min_util, 0.0)

    # ── Helpers ──────────────────────────────────────────────────────

    def _extract_watchlist(self, current_batch_id: int) -> list[dict]:
        """
        Return top-k active (non-stale) patterns sorted by avg_util desc.
        """
        stale_cutoff = current_batch_id - config.stale_limit
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT pattern_key, avg_util, last_seen_batch
                FROM pattern_tracker
                WHERE last_seen_batch >= ?
                ORDER BY avg_util DESC
                LIMIT ?
                """,
                (stale_cutoff, config.top_k),
            ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _pattern_utility_in_batch(
        pattern_items: list[str],
        batch: TransactionBatch,
    ) -> float:
        """
        Compute the total exact utility of a pattern across all
        transactions in a batch.

        A pattern's utility in a transaction is the sum of utilities
        of its constituent items (if all items are present).
        """
        total = 0.0
        pattern_set = set(pattern_items)
        for txn in batch.transactions:
            item_util = dict(zip(txn.items, txn.utilities))
            if pattern_set.issubset(item_util.keys()):
                total += sum(item_util[it] for it in pattern_items)
        return total
