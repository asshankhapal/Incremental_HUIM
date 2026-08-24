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
        batch_old: Optional[TransactionBatch],
    ) -> None:
        """
        Incrementally update prefix utilities and MRU values.

        Parameters
        ----------
        batch_new : transactions just added to the sliding window
        batch_old : transactions just evicted from the sliding window
        """
        if batch_new is not None:
            self._process_batch(batch_new, add=True)
        if batch_old is not None:
            self._process_batch(batch_old, add=False)
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

                # ── Global MRU ───────────────────────────────────
                remaining = sum(sorted_utils[idx + 1:])
                if add:
                    self.global_mru[item] = max(
                        self.global_mru.get(item, 0.0), remaining
                    )
                # NOTE: On removal we do NOT reduce MRU (it's a max-ever
                # approximation).  A full recompute can be done periodically
                # if precision matters.

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
