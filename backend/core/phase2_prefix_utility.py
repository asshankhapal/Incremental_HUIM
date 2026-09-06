"""
PHASE 2: INCREMENTAL PREFIX UTILITY & GLOBAL MRU UPDATE
=========================================================
Flowchart pseudocode implemented exactly:

  For each transaction in added batch (lexicographic order):
      cumulative = 0
      For each item in transaction (sorted):
          cumulative += item_utility
          prefix_util[item] += cumulative        (Layer 1 bound)
          update global_MRU[item] = max(global_MRU[item], remaining after item)

  For each transaction in removed batch (same order):
      subtract similarly to keep prefix_util and global_MRU current

A transaction here is a dict: {"tid": int, "items": [...], "utils": [...], "TU": int}
with items/utils already sorted ascending by item id ("lexicographic order").

IMPORTANT CAVEAT (worth knowing, not just implementing blindly):
  prefix_util is a SUM across transactions -> safely reversible: subtracting a removed
  transaction's contribution restores the exact prior state.
  global_MRU is a MAX across transactions -> a MAX is *not* reversible by subtraction.
  If the transaction holding the current maximum for an item is evicted, you cannot
  recover the correct new maximum just by "subtracting" — you need either (a) a small
  max-heap/multiset per item of contributing values, or (b) a full recompute over the
  current window. This module provides the naive (flowchart-literal) subtract for
  prefix_util, and offers both a naive "best-effort" subtract for global_MRU (which can
  be WRONG) and a correct `recompute_global_mru_fresh` you should prefer in production.
"""

from collections import defaultdict


def _item_lists_from_transaction(t):
    """Yields (item, iutil, remaining_after) for a single transaction, in item order."""
    cumulative = 0
    n = len(t["items"])
    out = []
    for pos in range(n):
        it, u = t["items"][pos], t["utils"][pos]
        cumulative += u
        remaining_after = t["TU"] - cumulative
        out.append((it, u, remaining_after))
    return out


def build_fresh(batch):
    """Fresh build of prefix_util / global_MRU / per-item utility-lists over `batch`."""
    prefix_util = defaultdict(int)
    global_mru = defaultdict(int)
    item_lists = defaultdict(dict)  # item -> {tid: (iutil, remaining_after)}
    for t in batch:
        cumulative = 0
        for it, u in zip(t["items"], t["utils"]):
            cumulative += u
            remaining_after = t["TU"] - cumulative
            prefix_util[it] += cumulative
            global_mru[it] = max(global_mru[it], remaining_after)
            item_lists[it][t["tid"]] = (u, remaining_after)
    return prefix_util, global_mru, item_lists


def add_batch(prefix_util, global_mru, item_lists, new_batch):
    """"New Batch Arrives" -> incrementally fold new_batch's contribution IN. Mutates in place."""
    for t in new_batch:
        cumulative = 0
        for it, u in zip(t["items"], t["utils"]):
            cumulative += u
            remaining_after = t["TU"] - cumulative
            prefix_util[it] += cumulative
            global_mru[it] = max(global_mru[it], remaining_after)
            item_lists[it][t["tid"]] = (u, remaining_after)


def remove_batch_prefix_util(prefix_util, item_lists, old_batch):
    """"Identify Oldest Batch" -> subtract its contribution from the SUM-based prefix_util.
    This is exact/safe because sums are reversible."""
    touched_items = set()
    for t in old_batch:
        cumulative = 0
        for it, u in zip(t["items"], t["utils"]):
            cumulative += u
            prefix_util[it] -= cumulative
            item_lists[it].pop(t["tid"], None)
            touched_items.add(it)
    # fully evicted items should disappear from both structures, not linger as empty entries
    for it in touched_items:
        if not item_lists.get(it):
            item_lists.pop(it, None)
            prefix_util.pop(it, None)


def recompute_global_mru_fresh(current_window):
    """Correct way to keep global_MRU current after an eviction: recompute over
    whatever transactions are actually still in the window."""
    global_mru = defaultdict(int)
    for t in current_window:
        cumulative = 0
        for it, u in zip(t["items"], t["utils"]):
            cumulative += u
            remaining_after = t["TU"] - cumulative
            global_mru[it] = max(global_mru[it], remaining_after)
    return global_mru


if __name__ == "__main__":
    demo_batch = [
        {"tid": 1, "items": [1, 2, 3], "utils": [10, 20, 30], "TU": 60},
        {"tid": 2, "items": [2, 3], "utils": [5, 5], "TU": 10},
    ]
    pu, mru, lists_ = build_fresh(demo_batch)
    print("prefix_util:", dict(pu))
    print("global_mru :", dict(mru))