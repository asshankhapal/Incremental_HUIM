"""
Phase 2 — Incremental Prefix Utility & Global MRU Update

For each transaction in the added batch (lexicographic order):
    cumulative = 0
    for each item (sorted):
        cumulative += item_utility
        prefix_util[item] += cumulative
        global_MRU[item] = max(global_MRU[item], remaining_after_item)

For removed batch: subtract symmetrically.
"""

from __future__ import annotations

import json
from typing import Optional

from database import get_db
from models.transaction import TransactionBatch


class PrefixUtilityUpdater:
    """Incrementally maintains prefix_util and global_MRU dictionaries."""

    def __init__(self) -> None:
        self.prefix_util: dict[str, float] = {}
        self.global_mru: dict[str, float] = {}
        self._load_from_db()

    # ── Public API ───────────────────────────────────────────────────

    def update(
        self,
        batch_new: Optional[TransactionBatch],
        evicted_batches: list[TransactionBatch],
        active_batch_ids: list[int],
    ) -> None:
        """
        Incrementally update prefix utilities and recalculate MRU values.

        Parameters
        ----------
        batch_new : transactions just added to the sliding window
        evicted_batches : list of batches just evicted from the sliding window
        active_batch_ids : list of active batch ids currently in the sliding window
        """
        if batch_new is not None:
            self._process_batch(batch_new, add=True)
            self._save_batch_mru(batch_new)
        for batch_old in evicted_batches:
            self._process_batch(batch_old, add=False)
            self._delete_batch_mru(batch_old.batch_id)
            
        # Re-aggregate global MRU from active batch MRUs
        self._reaggregate_global_mru(active_batch_ids)
        self._persist_to_db()

    # ── Internal ─────────────────────────────────────────────────────

    def _process_batch(self, batch: TransactionBatch, *, add: bool) -> None:
        """Process every transaction in a batch (add or subtract)."""
        sign = 1.0 if add else -1.0

        for txn in batch.transactions:
            # Sort items lexicographically (canonical order)
            paired = sorted(zip(txn.items, txn.utilities), key=lambda x: x[0])
            sorted_items = [p[0] for p in paired]
            sorted_utils = [p[1] for p in paired]

            cumulative = 0.0
            for idx, (item, util) in enumerate(zip(sorted_items, sorted_utils)):
                cumulative += util

                # ── Prefix utility (Layer 1 bound) ───────────────
                self.prefix_util[item] = self.prefix_util.get(item, 0.0) + sign * cumulative

    def _save_batch_mru(self, batch: TransactionBatch) -> None:
        """Compute and save MRU contributions for a new batch."""
        mru = {}
        for txn in batch.transactions:
            paired = sorted(zip(txn.items, txn.utilities), key=lambda x: x[0])
            sorted_items = [p[0] for p in paired]
            sorted_utils = [p[1] for p in paired]
            for idx, item in enumerate(sorted_items):
                remaining = sum(sorted_utils[idx + 1:])
                mru[item] = max(mru.get(item, 0.0), remaining)
                
        with get_db() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO batch_mru (batch_id, item, value) VALUES (?, ?, ?)",
                [(batch.batch_id, item, val) for item, val in mru.items()]
            )

    def _delete_batch_mru(self, batch_id: int) -> None:
        """Delete batch MRU records for the evicted batch."""
        with get_db() as conn:
            conn.execute("DELETE FROM batch_mru WHERE batch_id = ?", (batch_id,))

    def _reaggregate_global_mru(self, active_batch_ids: list[int]) -> None:
        """Recompute global_mru from active batch MRUs."""
        self.global_mru.clear()
        if not active_batch_ids:
            return
        placeholders = ",".join("?" for _ in active_batch_ids)
        with get_db() as conn:
            rows = conn.execute(
                f"""
                SELECT item, MAX(value) AS max_val
                FROM batch_mru
                WHERE batch_id IN ({placeholders})
                GROUP BY item
                """,
                active_batch_ids,
            ).fetchall()
        for r in rows:
            self.global_mru[r["item"]] = r["max_val"]

    # ── Persistence ──────────────────────────────────────────────────

    def _load_from_db(self) -> None:
        with get_db() as conn:
            for row in conn.execute("SELECT item, value FROM prefix_utility"):
                self.prefix_util[row["item"]] = row["value"]
            for row in conn.execute("SELECT item, value FROM global_mru"):
                self.global_mru[row["item"]] = row["value"]

    def _persist_to_db(self) -> None:
        with get_db() as conn:
            conn.execute("DELETE FROM prefix_utility")
            conn.executemany(
                "INSERT INTO prefix_utility (item, value) VALUES (?, ?)",
                list(self.prefix_util.items()),
            )
            conn.execute("DELETE FROM global_mru")
            conn.executemany(
                "INSERT INTO global_mru (item, value) VALUES (?, ?)",
                list(self.global_mru.items()),
            )
