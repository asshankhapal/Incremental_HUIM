"""API-facing adapter for the functional Phase 1-5 implementation.

The phase modules intentionally expose functions rather than the legacy classes the
web service used to import.  This adapter is the only compatibility layer between
the API/database boundary and those functions; it does not alter the algorithms.
"""

from __future__ import annotations

import json
import time

from config import config
from core.phase1_sliding_window import SlidingWindow
from core.phase2_prefix_utility import build_fresh
from core.phase3_hdkt import compute_hdkt_threshold
from core.phase4_topk_mining import mine_top_k
from core.phase5_validation import rank_and_output, update_hashmap
from database import get_db


class Pipeline:
    """Run one queued Redis batch through the existing functional phases."""

    def run(self) -> dict:
        from redis_client import redis_client

        raw_transactions = redis_client.lrange("huim:transaction_queue", 0, -1)
        if not raw_transactions:
            return {"status": "no_data", "message": "No queued transactions to process."}

        phase1 = SlidingWindow(W=config.batch_trigger_size, T_seconds=config.time_threshold)
        phase1.enqueue(raw_transactions)
        if not phase1.trigger_fired():
            return {"status": "no_trigger", "message": "Pipeline trigger conditions are not met."}
        raw_transactions, _ = phase1.flush_batch()

        run_id = self._log_start()
        timings: dict[str, float] = {}
        try:
            transactions = [json.loads(raw) for raw in raw_transactions]
            t0 = time.perf_counter()
            batch_id, batch_new, batch_old, hashmap = self._load_state(transactions)
            timings["phase1_ms"] = (time.perf_counter() - t0) * 1000

            t0 = time.perf_counter()
            prefix_util, global_mru, item_lists = build_fresh(batch_new)
            timings["phase2_ms"] = (time.perf_counter() - t0) * 1000

            t0 = time.perf_counter()
            min_util, watchlist = compute_hdkt_threshold(
                hashmap, batch_id, config.stale_limit, config.top_k, batch_new, batch_old
            )
            timings["phase3_ms"] = (time.perf_counter() - t0) * 1000

            t0 = time.perf_counter()
            top_k, stats = mine_top_k(
                item_lists, prefix_util, global_mru, config.top_k, start_min_util=min_util
            )
            timings["phase4_ms"] = (time.perf_counter() - t0) * 1000

            t0 = time.perf_counter()
            update_hashmap(hashmap, top_k, batch_id, config.hashmap_capacity, config.decay_factor)
            ranked = rank_and_output(hashmap, config.top_n_results)
            self._save_tracker(hashmap)
            timings["phase5_ms"] = (time.perf_counter() - t0) * 1000

            redis_client.ltrim("huim:transaction_queue", len(raw_transactions), -1)
            summary = {
                "run_id": run_id,
                "status": "success",
                "batch_new_id": batch_id,
                "batch_new_size": len(batch_new),
                "min_util_threshold": min_util,
                "patterns_discovered": len(top_k),
                "top_results": [
                    {"pattern": ",".join(map(str, itemset)), "avg_util": entry["avg_util"], "count": entry["count"]}
                    for itemset, entry in ranked
                ],
                "timings": timings,
                "dfs_stats": stats,
                "watchlist_size": len(watchlist),
            }
            self._log_finish(run_id, "success", summary)
            return summary
        except Exception as exc:
            summary = {"run_id": run_id, "status": "error", "error": str(exc)}
            self._log_finish(run_id, "error", summary)
            raise

    @staticmethod
    def _load_state(transactions: list[dict]) -> tuple[int, list[dict], list[dict], dict]:
        with get_db() as conn:
            cursor = conn.execute("INSERT INTO batches (status) VALUES ('processing')")
            batch_id = cursor.lastrowid
            previous = conn.execute(
                "SELECT MAX(batch_id) AS batch_id FROM batches WHERE batch_id < ? AND status = 'processed'",
                (batch_id,),
            ).fetchone()["batch_id"]

            batch_new = []
            for txn in transactions:
                items = txn["items"]
                utilities = txn["utilities"]
                if len(items) != len(utilities):
                    raise ValueError("Transaction items and utilities must have the same length.")
                order = sorted(range(len(items)), key=lambda index: str(items[index]))
                cursor = conn.execute(
                    "INSERT INTO transactions (batch_id, items, utilities) VALUES (?, ?, ?)",
                    (batch_id, json.dumps(items), json.dumps(utilities)),
                )
                batch_new.append({
                    "tid": cursor.lastrowid,
                    "items": [items[index] for index in order],
                    "utils": [utilities[index] for index in order],
                    "TU": sum(utilities),
                })

            batch_old = []
            if previous is not None:
                rows = conn.execute(
                    "SELECT tid, items, utilities FROM transactions WHERE batch_id = ?", (previous,)
                ).fetchall()
                for row in rows:
                    items, utilities = json.loads(row["items"]), json.loads(row["utilities"])
                    order = sorted(range(len(items)), key=lambda index: str(items[index]))
                    batch_old.append({
                        "tid": row["tid"], "items": [items[index] for index in order],
                        "utils": [utilities[index] for index in order], "TU": sum(utilities),
                    })
                conn.execute("UPDATE batches SET status = 'evicted' WHERE batch_id = ?", (previous,))

            conn.execute("UPDATE batches SET status = 'processed' WHERE batch_id = ?", (batch_id,))
            rows = conn.execute(
                "SELECT pattern_key, total_util, count, avg_util, last_seen_batch FROM pattern_tracker"
            ).fetchall()
            hashmap = {
                tuple(row["pattern_key"].split(",")): {
                    "total_util": row["total_util"], "count": row["count"],
                    "avg_util": row["avg_util"], "last_seen": row["last_seen_batch"],
                }
                for row in rows
            }
        return batch_id, batch_new, batch_old, hashmap

    @staticmethod
    def _save_tracker(hashmap: dict) -> None:
        with get_db() as conn:
            conn.execute("DELETE FROM pattern_tracker")
            conn.executemany(
                "INSERT INTO pattern_tracker (pattern_key, total_util, count, avg_util, last_seen_batch) VALUES (?, ?, ?, ?, ?)",
                [(",".join(map(str, itemset)), entry["total_util"], entry["count"], entry["avg_util"], entry["last_seen"])
                 for itemset, entry in hashmap.items()],
            )

    @staticmethod
    def _log_start() -> int:
        with get_db() as conn:
            return conn.execute("INSERT INTO pipeline_runs (status) VALUES ('running')").lastrowid

    @staticmethod
    def _log_finish(run_id: int, status: str, details: dict) -> None:
        with get_db() as conn:
            conn.execute(
                "UPDATE pipeline_runs SET finished_at = datetime('now'), status = ?, details = ? WHERE run_id = ?",
                (status, json.dumps(details), run_id),
            )
