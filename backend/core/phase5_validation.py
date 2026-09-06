"""
PHASE 5: HISTORICAL VALIDATION (HASHMAP UPDATE & RANKING)
============================================================
Flowchart boxes implemented here, in order:

  1. Input: Phase 4 patterns + current_batch
  2. Check: pattern already in HashMap?
       Yes -> Update Entry :  total_util += util; count += 1;
                               avg_util = total_util / count; last_seen = current_batch
       No  -> Create New Entry: total_util = util; count = 1;
                                 avg_util = util; last_seen = current_batch
  3. Decay Step (runs once per batch, for all UNSEEN patterns -- i.e. entries that
     already existed but were NOT among this batch's Phase 4 output):
        total_util *= 0.9 ; avg_util recalculated
  4. Capacity Check: HashMap size > K ?
        Yes -> evict pattern with lowest avg_util
        No  -> skip
  5. Rank & Output: sort by avg_util desc, return top-n recommendations
"""

DECAY_FACTOR = 0.9


def update_hashmap(hashmap, phase4_topk, current_batch, capacity_K, decay=DECAY_FACTOR):
    """
    hashmap       : dict itemset -> {"total_util","count","avg_util","last_seen"}  (mutated in place)
    phase4_topk   : list of (utility, itemset) from Phase 4 for this batch
    current_batch : int, the batch id just processed
    capacity_K    : max number of entries the HashMap may hold
    """
    seen_this_batch = set()

    # --- Step 2: update or create ---
    for util, itemset in phase4_topk:
        seen_this_batch.add(itemset)
        if itemset in hashmap:
            e = hashmap[itemset]
            e["total_util"] += util
            e["count"] += 1
            e["avg_util"] = e["total_util"] / e["count"]
            e["last_seen"] = current_batch
        else:
            hashmap[itemset] = {"total_util": util, "count": 1,
                                 "avg_util": util, "last_seen": current_batch}

    # --- Step 3: decay every pattern NOT touched this batch ---
    for itemset, e in hashmap.items():
        if itemset not in seen_this_batch:
            e["total_util"] *= decay
            e["avg_util"] = e["total_util"] / e["count"]

    # --- Step 4: capacity check / eviction ---
    while len(hashmap) > capacity_K:
        worst_itemset = min(hashmap.items(), key=lambda kv: kv[1]["avg_util"])[0]
        del hashmap[worst_itemset]

    return hashmap


def rank_and_output(hashmap, top_n):
    """Step 5: sort by avg_util desc, return top-n recommendations."""
    ranked = sorted(hashmap.items(), key=lambda kv: -kv[1]["avg_util"])
    return ranked[:top_n]


if __name__ == "__main__":
    hashmap = {(1, 2): {"total_util": 100, "count": 1, "avg_util": 100, "last_seen": 1}}
    phase4_out = [(90, (1, 2)), (50, (3, 4))]
    update_hashmap(hashmap, phase4_out, current_batch=2, capacity_K=10)
    for r in rank_and_output(hashmap, top_n=5):
        print(r)