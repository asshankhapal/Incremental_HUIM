"""
Phase 5 — Historical Validation (HashMap Update & Ranking)

For each pattern discovered in Phase 4:
    1. Check if pattern exists in HashMap.
    2. If yes → update: total_util += util, count += 1, avg_util = total/count,
       last_seen = current_batch.
    3. If no  → create new entry.
    4. Decay step (once per batch): for all *unseen* patterns,
       total_util *= decay_factor, recalculate avg_util.
    5. Capacity check: if HashMap size > K, evict pattern with lowest avg_util.
    6. Rank & output: sort by avg_util desc, return top-n.
"""

from __future__ import annotations

from config import config
from database import get_db
from models.pattern import PatternResult, TrackerEntry


class HistoricalValidator:
    """Maintains the global pattern tracker HashMap in SQLite."""

    def validate(
        self,
        discovered_patterns: list[PatternResult],
        current_batch_id: int,
    ) -> list[TrackerEntry]:
        """
        Run the full Phase 5 pipeline and return top-n ranked patterns.
        """
        if discovered_patterns:
            # Upsert all discovered patterns in a single batch transaction
            self._upsert_patterns_batch(discovered_patterns, current_batch_id)

        # Step 4: Decay unseen patterns
        self._decay_unseen(current_batch_id)

        # Step 5: Capacity check & eviction
        self._enforce_capacity()

        # Step 6: Rank and return
        return self._get_top_n()

    # ── Batched Upsert ──────────────────────────────────────────────

    @staticmethod
    def _upsert_patterns_batch(
        discovered_patterns: list[PatternResult],
        current_batch_id: int,
    ) -> None:
        """Upsert a batch of patterns using a single connection and batched statements."""
        keys = [p.pattern_key for p in discovered_patterns]
        placeholders = ",".join("?" for _ in keys)

        with get_db() as conn:
            # 1. Fetch existing counts and utilities for all keys in one query
            rows = conn.execute(
                f"SELECT pattern_key, total_util, count FROM pattern_tracker WHERE pattern_key IN ({placeholders})",
                keys,
            ).fetchall()

            existing = {r["pattern_key"]: (r["total_util"], r["count"]) for r in rows}

            updates = []
            inserts = []

            for pattern in discovered_patterns:
                key = pattern.pattern_key
                util = pattern.exact_utility

                if key in existing:
                    tot, cnt = existing[key]
                    new_tot = tot + util
                    new_cnt = cnt + 1
                    new_avg = new_tot / new_cnt
                    updates.append((new_tot, new_cnt, new_avg, current_batch_id, key))
                else:
                    inserts.append((key, util, util, current_batch_id))

            # 2. Bulk updates
            if updates:
                conn.executemany(
                    """
                    UPDATE pattern_tracker
                    SET total_util = ?, count = ?, avg_util = ?, last_seen_batch = ?
                    WHERE pattern_key = ?
                    """,
                    updates,
                )

            # 3. Bulk inserts
            if inserts:
                conn.executemany(
                    """
                    INSERT INTO pattern_tracker
                        (pattern_key, total_util, count, avg_util, last_seen_batch)
                    VALUES (?, ?, 1, ?, ?)
                    """,
                    inserts,
                )

    # ── Step 4: Decay ────────────────────────────────────────────────

    @staticmethod
    def _decay_unseen(current_batch_id: int) -> None:
        """Apply decay factor to all patterns NOT seen in this batch."""
        with get_db() as conn:
            # First, decay the total utility of unseen patterns exactly once
            conn.execute(
                """
                UPDATE pattern_tracker
                SET total_util = total_util * ?
                WHERE last_seen_batch < ?
                """,
                (config.decay_factor, current_batch_id),
            )
            # Second, recalculate avg_util based on the new total utility
            conn.execute(
                """
                UPDATE pattern_tracker
                SET avg_util = CASE WHEN count > 0 THEN total_util / count ELSE 0.0 END
                WHERE last_seen_batch < ?
                """,
                (current_batch_id,),
            )

    # ── Step 5: Capacity eviction ────────────────────────────────────

    @staticmethod
    def _enforce_capacity() -> None:
        """Evict lowest-avg_util patterns if HashMap exceeds capacity."""
        with get_db() as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM pattern_tracker"
            ).fetchone()["cnt"]

            if count <= config.hashmap_capacity:
                return

            excess = count - config.hashmap_capacity
            conn.execute(
                """
                DELETE FROM pattern_tracker
                WHERE pattern_key IN (
                    SELECT pattern_key FROM pattern_tracker
                    ORDER BY avg_util ASC
                    LIMIT ?
                )
                """,
                (excess,),
            )

    # ── Step 6: Ranking ──────────────────────────────────────────────

    @staticmethod
    def _get_top_n() -> list[TrackerEntry]:
        """Return top-n patterns ranked by avg_util descending."""
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT pattern_key, total_util, count, avg_util, last_seen_batch
                FROM pattern_tracker
                ORDER BY avg_util DESC
                LIMIT ?
                """,
                (config.top_n_results,),
            ).fetchall()
        return [
            TrackerEntry(
                pattern_key=r["pattern_key"],
                total_util=r["total_util"],
                count=r["count"],
                avg_util=r["avg_util"],
                last_seen_batch=r["last_seen_batch"],
            )
            for r in rows
        ]
