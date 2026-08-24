"""
Pipeline Orchestrator — wires Phases 1 → 5 together.

Called by the mining service when the pipeline is triggered
(either automatically or via API).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from database import get_db
from models.pattern import TrackerEntry
from core.phase1_sliding_window import SlidingWindow
from core.phase2_prefix_utility import PrefixUtilityUpdater
from core.phase3_hdkt import HDkTCalculator
from core.phase4_topk_mining import TopKMiner
from core.phase5_validation import HistoricalValidator

logger = logging.getLogger(__name__)


class Pipeline:
    """
    End-to-end pipeline orchestrator.

    Sequence:
        Phase 1 → sliding window update (batch_new, batch_old)
        Phase 2 → incremental prefix utility & MRU
        Phase 3 → HDkT threshold
        Phase 4 → top-k DFS mining
        Phase 5 → historical validation & ranking
    """

    def __init__(self) -> None:
        self.sliding_window = SlidingWindow()
        self.prefix_updater = PrefixUtilityUpdater()
        self.hdkt = HDkTCalculator()
        self.validator = HistoricalValidator()

    def run(self) -> dict:
        """
        Execute the full 5-phase pipeline once.

        Returns a summary dict with timing, counts, and top results.
        """
        run_id = self._log_start()
        timings: dict[str, float] = {}
        summary: dict = {"run_id": run_id}

        try:
            import time

            # ── Phase 1: Sliding Window ──────────────────────────
            t0 = time.perf_counter()
            batch_new, batch_old = self.sliding_window.update()
            timings["phase1_ms"] = (time.perf_counter() - t0) * 1000

            if batch_new is None:
                summary["status"] = "no_data"
                summary["message"] = "No queued batches to process."
                self._log_finish(run_id, "no_data", summary)
                return summary

            current_batch_id = batch_new.batch_id
            summary["batch_new_id"] = current_batch_id
            summary["batch_new_size"] = batch_new.size
            summary["batch_old_id"] = batch_old.batch_id if batch_old else None

            logger.info(
                "Phase 1 done: added batch %d (%d txns), evicted batch %s",
                current_batch_id,
                batch_new.size,
                batch_old.batch_id if batch_old else "none",
            )

            # ── Phase 2: Prefix Utility & MRU ────────────────────
            t0 = time.perf_counter()
            self.prefix_updater.update(batch_new, batch_old)
            timings["phase2_ms"] = (time.perf_counter() - t0) * 1000
            logger.info("Phase 2 done: %d items tracked", len(self.prefix_updater.prefix_util))

            # ── Phase 3: HDkT Threshold ──────────────────────────
            t0 = time.perf_counter()
            current_min_util = self.hdkt.compute_threshold(
                current_batch_id, batch_new, batch_old
            )
            timings["phase3_ms"] = (time.perf_counter() - t0) * 1000
            summary["min_util_threshold"] = current_min_util
            logger.info("Phase 3 done: min_util = %.4f", current_min_util)

            # ── Phase 4: Top-k Mining (DFS) ──────────────────────
            t0 = time.perf_counter()
            miner = TopKMiner(
                prefix_util=self.prefix_updater.prefix_util,
                global_mru=self.prefix_updater.global_mru,
                current_min_util=current_min_util,
                active_batch_ids=self.sliding_window.active_batch_ids,
            )
            discovered = miner.mine()
            timings["phase4_ms"] = (time.perf_counter() - t0) * 1000
            summary["patterns_discovered"] = len(discovered)
            logger.info("Phase 4 done: %d HUIs discovered", len(discovered))

            # ── Phase 5: Historical Validation ───────────────────
            t0 = time.perf_counter()
            top_results = self.validator.validate(discovered, current_batch_id)
            timings["phase5_ms"] = (time.perf_counter() - t0) * 1000
            summary["top_results"] = [
                {
                    "pattern": r.pattern_key,
                    "avg_util": round(r.avg_util, 4),
                    "count": r.count,
                }
                for r in top_results
            ]
            logger.info("Phase 5 done: top-%d results returned", len(top_results))

            summary["timings"] = timings
            summary["status"] = "success"
            self._log_finish(run_id, "success", summary)

        except Exception as exc:
            logger.exception("Pipeline run %d failed", run_id)
            summary["status"] = "error"
            summary["error"] = str(exc)
            self._log_finish(run_id, "error", summary)
            raise

        return summary

    # ── Run logging ──────────────────────────────────────────────────

    @staticmethod
    def _log_start() -> int:
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO pipeline_runs (status) VALUES ('running')"
            )
            return cursor.lastrowid  # type: ignore[return-value]

    @staticmethod
    def _log_finish(run_id: int, status: str, details: dict) -> None:
        with get_db() as conn:
            conn.execute(
                """
                UPDATE pipeline_runs
                SET finished_at = datetime('now'), status = ?, details = ?
                WHERE run_id = ?
                """,
                (status, json.dumps(details), run_id),
            )
