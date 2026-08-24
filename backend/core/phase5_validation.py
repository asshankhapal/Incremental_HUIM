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
        # Steps 1-3: Upsert each discovered pattern
        for pattern in discovered_patterns:
            self._upsert_pattern(pattern, current_batch_id)

        # Step 4: Decay unseen patterns
        self._decay_unseen(current_batch_id)

        # Step 5: Capacity check & eviction
        self._enforce_capacity()

        # Step 6: Rank and return
        return self._get_top_n()

    # ── Steps 1-3: Upsert ───────────────────────────────────────────

    @staticmethod
    def _upsert_pattern(pattern: PatternResult, current_batch_id: int) -> None:
        key = pattern.pattern_key
        util = pattern.exact_utility

        with get_db() as conn:
            row = conn.execute(
                "SELECT total_util, count FROM pattern_tracker WHERE pattern_key = ?",
                (key,),
            ).fetchone()

            if row is not None:
                # Update existing
                new_total = row["total_util"] + util
                new_count = row["count"] + 1
                new_avg = new_total / new_count
                conn.execute(
                    """
                    UPDATE pattern_tracker
                    SET total_util = ?, count = ?, avg_util = ?, last_seen_batch = ?
                    WHERE pattern_key = ?
                    """,
                    (new_total, new_count, new_avg, current_batch_id, key),
                )
            else:
                # Create new entry
                conn.execute(
                    """
                    INSERT INTO pattern_tracker
                        (pattern_key, total_util, count, avg_util, last_seen_batch)
                    VALUES (?, ?, 1, ?, ?)
                    """,
                    (key, util, util, current_batch_id),
                )

    # ── Step 4: Decay ────────────────────────────────────────────────

    @staticmethod
    def _decay_unseen(current_batch_id: int) -> None:
        """Apply decay factor to all patterns NOT seen in this batch."""
        with get_db() as conn:
            conn.execute(
                """
                UPDATE pattern_tracker
                SET total_util = total_util * ?,
                    avg_util   = CASE WHEN count > 0
                                      THEN (total_util * ?) / count
                                      ELSE 0.0 END
                WHERE last_seen_batch < ?
                """,
                (config.decay_factor, config.decay_factor, current_batch_id),
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
