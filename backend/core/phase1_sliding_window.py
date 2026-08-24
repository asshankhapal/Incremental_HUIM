"""
Phase 1 — Sliding Window Update (Trigger-Based)

Maintains a bounded sliding window of transaction batches.
Evaluates two trigger conditions (time elapsed ≥ T, queued txns ≥ W)
and, when fired, adds the newest batch and evicts the oldest.
"""

from __future__ import annotations

import json
import time
from collections import deque
from typing import Optional

from config import config
from database import get_db
from models.transaction import Transaction, TransactionBatch


class SlidingWindow:
    """
    Manages the sliding window of transaction batches.

    The window is a deque of batch_ids.  On each trigger:
      1. Append the newest queued batch.
      2. If the window exceeds `window_size` (in total transactions),
         pop the oldest batch.
    """

    def __init__(self) -> None:
        self._window: deque[int] = deque()          # batch_ids in window
        self._last_run_time: float = time.time()
        self._reload_window()

    def should_trigger(self) -> bool:
        """Return True if either trigger condition is satisfied."""
        time_elapsed = time.time() - self._last_run_time >= config.time_threshold
        queued_count = self._queued_transaction_count()
        volume_met = queued_count >= config.batch_trigger_size
        return time_elapsed or volume_met

    def update(self) -> tuple[Optional[TransactionBatch], list[TransactionBatch]]:
        """
        Execute the sliding-window step.

        Returns
        -------
        (batch_new, evicted_batches)
            batch_new : the batch just added to the window (or None)
            evicted_batches : list of batches just evicted from the window
        """
        self._last_run_time = time.time()

        # Find the next queued batch
        batch_new = self._pop_next_queued_batch()
        if batch_new is None:
            return None, []

        # Add to the window
        self._window.append(batch_new.batch_id)
        self._mark_batch_status(batch_new.batch_id, "active")

        # Evict the oldest batches if window is over capacity
        evicted_batches: list[TransactionBatch] = []
        while self._window_transaction_count() > config.window_size and self._window:
            oldest_id = self._window.popleft()
            batch_old = self._load_batch(oldest_id)
            self._mark_batch_status(oldest_id, "evicted")
            evicted_batches.append(batch_old)

        return batch_new, evicted_batches

    
    def _reload_window(self) -> None:
        """Reload the window from DB (batches with status='active')."""
        with get_db() as conn:
            rows = conn.execute(
                "SELECT batch_id FROM batches WHERE status='active' ORDER BY batch_id"
            ).fetchall()
            self._window = deque(r["batch_id"] for r in rows)

    def _queued_transaction_count(self) -> int:
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(cnt), 0) AS total
                FROM (
                    SELECT COUNT(*) AS cnt
                    FROM transactions t
                    JOIN batches b ON t.batch_id = b.batch_id
                    WHERE b.status = 'queued'
                )
                """
            ).fetchone()
            return row["total"]

    def _window_transaction_count(self) -> int:
        """Total transactions currently in the window."""
        if not self._window:
            return 0
        placeholders = ",".join("?" for _ in self._window)
        with get_db() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM transactions WHERE batch_id IN ({placeholders})",
                list(self._window),
            ).fetchone()
            return row["cnt"]

    def _pop_next_queued_batch(self) -> Optional[TransactionBatch]:
        """Load the oldest queued batch and return it."""
        with get_db() as conn:
            row = conn.execute(
                "SELECT batch_id FROM batches WHERE status='queued' ORDER BY batch_id LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            return self._load_batch(row["batch_id"])

    def _load_batch(self, batch_id: int) -> TransactionBatch:
        """Load all transactions for a given batch_id."""
        with get_db() as conn:
            rows = conn.execute(
                "SELECT tid, items, utilities FROM transactions WHERE batch_id = ?",
                (batch_id,),
            ).fetchall()
        txns = [
            Transaction(
                tid=r["tid"],
                items=json.loads(r["items"]),
                utilities=json.loads(r["utilities"]),
                batch_id=batch_id,
            )
            for r in rows
        ]
        return TransactionBatch(batch_id=batch_id, transactions=txns)

    @staticmethod
    def _mark_batch_status(batch_id: int, status: str) -> None:
        with get_db() as conn:
            conn.execute(
                "UPDATE batches SET status = ? WHERE batch_id = ?",
                (status, batch_id),
            )

    @property
    def active_batch_ids(self) -> list[int]:
        return list(self._window)
