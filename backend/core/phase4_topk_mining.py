"""
Phase 4 — Top-k Mining with Dual Pruning (DFS)

1. Build Header Table (items in lexicographic order).
2. For each item X in Header Table:
     - Layer 1 prune: skip X if prefix_util[X] < current_min_util.
     - Initialize utility list for X.
     - Call DFS_Extend(X).
3. DFS_Extend(P):
     For each item Y after last item in P (lexicographic):
       - Join utility lists: P + Y → PY
       - Compute exact_util(PY).
       - If exact_util(PY) ≥ current_min_util → HUI! Add to priority queue.
       - Compute UB = exact_util(P) + global_MRU[last_item].
         Layer 2 prune: if UB < current_min_util → skip Y.
       - Else recursively call DFS_Extend(PY).
     - If priority queue size > k: pop lowest, update current_min_util.
"""

from __future__ import annotations

import heapq
import json
from typing import Optional

from config import config
from database import get_db
from models.transaction import (
    Transaction,
    UtilityList,
    UtilityListEntry,
)
from models.pattern import PatternResult


class TopKMiner:
    """
    Depth-first top-k high-utility itemset miner with dual pruning.
    """

    def __init__(
        self,
        prefix_util: dict[str, float],
        global_mru: dict[str, float],
        current_min_util: float,
        active_batch_ids: list[int],
    ) -> None:
        self.prefix_util = prefix_util
        self.global_mru = global_mru
        self.min_util = current_min_util
        self.active_batch_ids = active_batch_ids

        # Min-heap of (-utility, pattern_key) so we can pop lowest
        self._topk_heap: list[tuple[float, str]] = []
        self._results: list[PatternResult] = []

    # ── Public API ───────────────────────────────────────────────────

    def mine(self) -> list[PatternResult]:
        """Run the full Phase 4 mining algorithm and return discovered HUIs."""
        transactions = self._load_active_transactions()
        if not transactions:
            return []

        # Pre-sort items and utilities for each transaction once
        for txn in transactions:
            paired = sorted(zip(txn.items, txn.utilities), key=lambda x: x[0])
            txn.items = [p[0] for p in paired]
            txn.utilities = [p[1] for p in paired]

        # Build initial utility lists for single items (Header Table) in a single pass
        item_uls: dict[str, UtilityList] = {}
        for txn in transactions:
            n = len(txn.utilities)
            # Precompute suffix sums of utilities for fast remaining utility lookup
            suffix_sums = [0.0] * (n + 1)
            for idx in range(n - 1, -1, -1):
                suffix_sums[idx] = suffix_sums[idx + 1] + txn.utilities[idx]

            for idx, item in enumerate(txn.items):
                # ── Layer 1 prune ────────────────────────────────────
                if self.prefix_util.get(item, 0.0) < self.min_util:
                    continue  # prune entire branch
                
                if item not in item_uls:
                    item_uls[item] = UtilityList(pattern=(item,))
                
                exact = txn.utilities[idx]
                remaining = suffix_sums[idx + 1]
                item_uls[item].entries.append(
                    UtilityListEntry(tid=txn.tid, exact_util=exact, remaining_util=remaining)
                )

        # Register all single-item patterns first to raise the min_util threshold immediately.
        # This prevents exploring the exponential combination space with min_util = 0.0.
        for ul in item_uls.values():
            self._check_and_register(ul)

        # Sort items by prefix utility descending for optimal DFS search order and faster pruning
        sorted_items = sorted(item_uls.keys(), key=lambda x: self.prefix_util.get(x, 0.0), reverse=True)

        # DFS from each surviving single-item pattern
        for i, item in enumerate(sorted_items):
            ul = item_uls[item]
            extensions = [item_uls[sorted_items[j]] for j in range(i + 1, len(sorted_items))]
            self._dfs_extend(ul, extensions, transactions)

        return self._results

    # ── DFS extension ────────────────────────────────────────────────

    def _dfs_extend(
        self,
        ul_p: UtilityList,
        extensions: list[UtilityList],
        transactions: list[Transaction],
    ) -> None:
        """Recursively extend pattern P with each candidate item Y."""
        for i, ul_y in enumerate(extensions):
            # Join utility lists  P ∪ Y → PY
            ul_py = self._join_utility_lists(ul_p, ul_y, transactions)

            exact = ul_py.sum_exact_util

            # ── Layer 2 prune (upper-bound check) ────────────────
            ub = ul_py.upper_bound
            if ub < self.min_util:
                continue  # prune this branch

            # Check if PY is a HUI
            self._check_and_register(ul_py)

            # Recurse deeper
            further = extensions[i + 1:]
            self._dfs_extend(ul_py, further, transactions)

    # ── Utility list construction ────────────────────────────────────

    def _build_initial_ul(
        self, item: str, transactions: list[Transaction]
    ) -> UtilityList:
        """Build the utility list for a single item from all active txns."""
        ul = UtilityList(pattern=(item,))
        for txn in transactions:
            if item in txn.items:
                idx = txn.items.index(item)
                exact = txn.utilities[idx]
                remaining = sum(txn.utilities[idx + 1:])
                ul.entries.append(
                    UtilityListEntry(tid=txn.tid, exact_util=exact, remaining_util=remaining)
                )
        return ul

    def _join_utility_lists(
        self,
        ul_p: UtilityList,
        ul_y: UtilityList,
        transactions: list[Transaction],
    ) -> UtilityList:
        """
        Join utility lists of pattern P and single item Y to get PY.
        Only transactions present in BOTH lists contribute.
        """
        new_pattern = ul_p.pattern + ul_y.pattern[-1:]
        ul_py = UtilityList(pattern=new_pattern)

        # Two-pointer join for sorted tids
        i, j = 0, 0
        n_p, n_y = len(ul_p.entries), len(ul_y.entries)
        while i < n_p and j < n_y:
            ep = ul_p.entries[i]
            ey = ul_y.entries[j]
            if ep.tid == ey.tid:
                exact = ep.exact_util + ey.exact_util
                remaining = ey.remaining_util
                ul_py.entries.append(
                    UtilityListEntry(tid=ep.tid, exact_util=exact, remaining_util=remaining)
                )
                i += 1
                j += 1
            elif ep.tid < ey.tid:
                i += 1
            else:
                j += 1

        return ul_py

    # ── Heap / result management ─────────────────────────────────────

    def _check_and_register(self, ul: UtilityList) -> None:
        """Add pattern to top-k heap if its exact utility ≥ threshold."""
        exact = ul.sum_exact_util
        if exact < self.min_util:
            return

        pattern_key = ",".join(ul.pattern)
        result = PatternResult(pattern=ul.pattern, exact_utility=exact)

        # Push into min-heap (we keep the *k largest*, so heap root = smallest)
        heapq.heappush(self._topk_heap, (exact, pattern_key))
        self._results.append(result)

        # If we have more than k, pop the smallest and raise threshold
        if len(self._topk_heap) > config.top_k:
            popped = heapq.heappop(self._topk_heap)
            self.min_util = self._topk_heap[0][0]  # new k-th value
            # Remove from results list
            self._results = [
                r for r in self._results if r.pattern_key != popped[1]
            ]

    # ── Data loading ─────────────────────────────────────────────────

    def _load_active_transactions(self) -> list[Transaction]:
        """Load all transactions in the current active window."""
        if not self.active_batch_ids:
            return []
        placeholders = ",".join("?" for _ in self.active_batch_ids)
        with get_db() as conn:
            rows = conn.execute(
                f"""
                SELECT tid, batch_id, items, utilities
                FROM transactions
                WHERE batch_id IN ({placeholders})
                """,
                self.active_batch_ids,
            ).fetchall()
        return [
            Transaction(
                tid=r["tid"],
                items=json.loads(r["items"]),
                utilities=json.loads(r["utilities"]),
                batch_id=r["batch_id"],
            )
            for r in rows
        ]
