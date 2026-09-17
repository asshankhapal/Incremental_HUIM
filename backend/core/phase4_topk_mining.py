"""
PHASE 4: TOP-k MINING WITH DUAL PRUNING (DFS)
================================================
Flowchart boxes implemented here:

  Build Header Table (items in lexicographic order)
  For each item X:
      prefix_util[X] >= current_min_util ?
          NO  -> Prune entire branch (skip X and all its supersets)     [Layer 1]
          YES -> Initialize utility list for single item X -> Call DFS_Extend(X)

  DFS_Extend(P):
      For each item Y after last item in lexicographic order:
          Join utility lists P + Y -> PY
          Compute exact utility of PY
          exact_util(PY) >= current_min_util ?
              YES -> HUI! -> Add to priority queue (max-heap of top-k)
                     If queue size > k: pop lowest, update current_min_util = new k-th utility
              NO  -> Not HUI but may extend
          At each extension: compute UB = exact_util(PY) + global_MRU[last_item]  [Layer 2]
          UB >= current_min_util ?
              YES -> Recursively call DFS_Extend(PY)
              NO  -> Prune branch (skip Y)
"""

import heapq


def join_utility_lists(p_list, y_list):
    """Standard utility-list join (HUI-Miner style): for tids common to both P and Y,
    exact_util(PY, tid) = exact_util(P, tid) + exact_util(Y, tid);
    remaining_util(PY, tid) = remaining_util(Y, tid)  (Y is the last item added, everything
    after it in the fixed item order is still 'remaining' regardless of what's already in P)."""
    out = {}
    for tid, (p_i, _p_r) in p_list.items():
        if tid in y_list:
            y_i, y_r = y_list[tid]
            out[tid] = (p_i + y_i, y_r)
    return out


def exact_utility(util_list):
    return sum(iutil for iutil, _rutil in util_list.values())


class TopKHeap:
    """Min-heap of size <= k tracking the current top-k HUIs by exact utility.
    heap[0] is always the smallest of the current top-k, i.e. current_min_util once full."""

    def __init__(self, k):
        self.k = k
        self.heap = []
        self.current_min_util = 0  # 0 (or the HDkT-provided starting threshold) until full

    def offer(self, itemset, utility):
        if len(self.heap) < self.k:
            heapq.heappush(self.heap, (utility, itemset))
            if len(self.heap) == self.k:
                self.current_min_util = self.heap[0][0]
        elif utility > self.heap[0][0]:
            heapq.heapreplace(self.heap, (utility, itemset))
            self.current_min_util = self.heap[0][0]

    def results(self):
        return sorted(self.heap, key=lambda z: -z[0])


def mine_top_k(item_lists, prefix_util, global_mru, k, start_min_util=0,
               max_depth=8, node_budget=500_000):
    """
    item_lists   : dict item -> {tid: (iutil, remaining_util)}   (built in Phase 2)
    prefix_util  : dict item -> Layer-1 bound                     (built in Phase 2)
    global_mru   : dict item -> Layer-2 bound ingredient           (built in Phase 2)
    k            : how many top itemsets to keep
    start_min_util : initial current_min_util. Pass 0 on cold start, or the value
                      produced by Phase 3 (compute_hdkt_threshold) otherwise.
    max_depth    : maximum itemset size to explore (prevents exponential blowup)
    node_budget  : stop DFS after this many nodes to guarantee bounded runtime

    Returns (top_k_list, stats) where top_k_list is [(utility, itemset), ...] descending,
    and stats reports pruning activity for diagnostics.
    """
    header_table = sorted(item_lists.keys())  # "Header Table (items in lexicographic order)"
    topk = TopKHeap(k)
    topk.current_min_util = start_min_util
    stats = {"nodes": 0, "hui_found": 0, "pruned_layer1": 0, "pruned_layer2_ub": 0,
             "empty_join": 0, "pruned_depth": 0, "budget_exhausted": False}

    def dfs_extend(p_itemset, p_list, last_item, depth):
        if depth >= max_depth:
            stats["pruned_depth"] += 1
            return
        for y in header_table:
            if stats["nodes"] >= node_budget:
                stats["budget_exhausted"] = True
                return
            if y <= last_item:
                continue  # only extend with items AFTER last_item in the fixed order
            stats["nodes"] += 1
            y_list = item_lists[y]
            py_list = join_utility_lists(p_list, y_list)
            if not py_list:
                stats["empty_join"] += 1
                continue  # P and Y never co-occur -> itemset has 0 support, discard

            py_itemset = p_itemset + (y,)
            util = exact_utility(py_list)

            if util >= topk.current_min_util:
                stats["hui_found"] += 1
                topk.offer(py_itemset, util)   # "HUI! -> add to priority queue"
            # else: "Not HUI but may extend" -- fall through to the UB check regardless

            # Upper bound: exact util + sum of remaining utilities (tighter than global_mru alone)
            remaining_sum = sum(rutil for _iutil, rutil in py_list.values())
            ub = min(util + global_mru.get(y, 0), util + remaining_sum)   # Layer 2 bound
            if ub >= topk.current_min_util:
                dfs_extend(py_itemset, py_list, y, depth + 1)     # "Recursively call DFS_Extend(PY)"
            else:
                stats["pruned_layer2_ub"] += 1          # "Prune branch (skip Y)"

    for x in header_table:
        if stats["nodes"] >= node_budget:
            stats["budget_exhausted"] = True
            break
        if prefix_util[x] < topk.current_min_util:
            stats["pruned_layer1"] += 1
            continue  # "Prune entire branch (skip X and all its supersets)"

        x_list = item_lists[x]
        util = exact_utility(x_list)
        if util >= topk.current_min_util:
            stats["hui_found"] += 1
            topk.offer((x,), util)

        dfs_extend((x,), x_list, x, 1)   # "Call DFS_Extend(X) with its utility list"

    return topk.results(), stats


if __name__ == "__main__":
    # tiny smoke test: two transactions sharing items 2,3
    item_lists = {
        1: {10: (10, 50)},
        2: {10: (20, 30), 11: (5, 5)},
        3: {10: (30, 0), 11: (5, 0)},
    }
    prefix_util = {1: 10, 2: 55, 3: 65}
    global_mru = {1: 50, 2: 30, 3: 0}
    top_k, stats = mine_top_k(item_lists, prefix_util, global_mru, k=3, start_min_util=0)
    print("top-k:", top_k)
    print("stats:", stats)