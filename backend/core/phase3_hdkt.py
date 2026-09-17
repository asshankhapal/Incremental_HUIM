"""
PHASE 3: HDkT (HISTORICAL DECAY-k THRESHOLD)
==============================================
Flowchart boxes implemented here, in order:

  1. System Inputs: HashMap (from Phase 5), Batchnew (exact utils of new txns),
     Batchold (exact utils of evicted txns)
  2. Step 1: Active Leaderboard Extraction & Stale Filtering
       - drop P if (current_batch - P.last_seen_batch) > stale_limit
       - from what's left, keep exactly k patterns with highest avg_util  (Top-k Active Watchlist)
  3. Step 2: Decay-Smoothed Delta Projection  (O(k) time)
       - Projected_U(P) = P.avg_util + U(P, Batchnew) - U(P, Batchold)
  4. Step 3: Instant Threshold Calculation  (O(1) time)
       - current_min_util = min(Projected_U(P1), ..., Projected_U(Pk))
  5. Output: current_min_util feeds Phase 4 as the pruning boundary for
     Layer 1 (prefix_util[X] < min_util -> prune) and Layer 2 (UB <= min_util -> prune)
"""


def stale_filter(hashmap, current_batch, stale_limit):
    """Step 1a: drop patterns not seen recently enough."""
    return {p: e for p, e in hashmap.items()
            if (current_batch - e["last_seen"]) <= stale_limit}


def extract_watchlist(active_patterns, k):
    """Step 1b: exactly k patterns with the highest historical avg_util."""
    ranked = sorted(active_patterns.items(), key=lambda kv: -kv[1]["avg_util"])
    return ranked[:k]


def itemset_utility_in_batch(itemset, batch, _cache={}):
    """U(P, Batch): exact utility of itemset P if evaluated against a given batch's
    transactions (0 if P is not fully supported by any transaction in that batch).
    Uses a per-batch cache of pre-built item sets and utility maps for speed."""
    # Build a cache key from batch identity (id is stable within one call chain)
    batch_key = id(batch)
    if batch_key not in _cache:
        indexed = []
        for t in batch:
            item_set = frozenset(t["items"])
            util_map = dict(zip(t["items"], t["utils"]))
            indexed.append((item_set, util_map))
        _cache[batch_key] = indexed
        # Keep cache small: only hold last 2 batches
        if len(_cache) > 2:
            oldest = next(iter(_cache))
            del _cache[oldest]
    indexed = _cache[batch_key]

    itemset_set = set(itemset)
    total = 0
    for item_set, util_map in indexed:
        if itemset_set.issubset(item_set):
            total += sum(util_map[i] for i in itemset)
    return total


def project_utility(pattern_entry, itemset, batch_new, batch_old):
    """Step 2: Projected_U(P) = avg_util + U(P,new) - U(P,old)."""
    u_new = itemset_utility_in_batch(itemset, batch_new)
    u_old = itemset_utility_in_batch(itemset, batch_old)
    return pattern_entry["avg_util"] + u_new - u_old, u_new, u_old


def compute_hdkt_threshold(hashmap, current_batch, stale_limit, k, batch_new, batch_old):
    """
    Runs all of Phase 3 end to end.
    Returns (current_min_util, watchlist_with_projections) where the latter is a list of
    (itemset, projected_utility, u_new, u_old) for transparency/debugging.
    """
    active = stale_filter(hashmap, current_batch, stale_limit)
    watchlist = extract_watchlist(active, k)

    if not watchlist:
        # cold start: no history yet -> no pruning boundary
        return 0, []

    details = []
    projections = []
    for itemset, entry in watchlist:
        proj, u_new, u_old = project_utility(entry, itemset, batch_new, batch_old)
        projections.append(proj)
        details.append((itemset, proj, u_new, u_old))

    current_min_util = min(projections)
    return current_min_util, details


if __name__ == "__main__":
    hashmap = {
        (1, 2): {"total_util": 100, "count": 1, "avg_util": 100, "last_seen": 1},
        (3, 4): {"total_util": 80, "count": 1, "avg_util": 80, "last_seen": 1},
    }
    batch_new = [{"tid": 11, "items": [1, 2, 5], "utils": [60, 50, 10], "TU": 120}]
    batch_old = [{"tid": 1, "items": [1, 2], "utils": [40, 60], "TU": 100}]
    thr, details = compute_hdkt_threshold(hashmap, current_batch=2, stale_limit=1, k=2,
                                           batch_new=batch_new, batch_old=batch_old)
    print("threshold:", thr)
    for d in details:
        print(d)