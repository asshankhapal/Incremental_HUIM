"""
MAIN PIPELINE — wires Phases 1-5 together.
No dataset is built into this file. You provide the transactions yourself, either:

  1) From a file:
       python3 main_pipeline.py --file my_transactions.txt

  2) By pasting into stdin (end with Ctrl+D on Linux/Mac, Ctrl+Z then Enter on Windows):
       python3 main_pipeline.py
       (then paste your lines, then EOF)

INPUT FORMAT (one transaction per line):
    item1 item2 item3 ... : TU : util1 util2 util3 ...
  e.g.
    308 475 1130 1350 1440:3239:872 783 465 276 843
  Items and per-item utilities must be in the same order and the utilities must sum to TU.

You can tune the algorithm's parameters from the command line — see `--help`.
Transactions are fed into the sliding window ONE AT A TIME to simulate a real stream.
Whenever Condition 2 (queue size >= W) fires, a batch is cut and Phases 2-5 run on it.
Any leftover transactions still queued when the input ends are flushed as one final
batch (standing in for "Condition 1: time elapsed" firing at the end of the stream).
"""

import argparse
import sys

from phase1_sliding_window import SlidingWindow
from phase2_prefix_utility_mru import build_fresh, add_batch, remove_batch_prefix_util, recompute_global_mru_fresh
from phase3_hdkt import compute_hdkt_threshold
from phase4_topk_dfs_mining import mine_top_k
from phase5_historical_validation import update_hashmap, rank_and_output


def parse_transactions(lines):
    """Parses 'items:TU:utils' lines into transaction dicts, sorted into a fixed
    ascending item-id order (the "lexicographic order" the flowchart refers to)."""
    transactions = []
    for lineno, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            items_s, tu_s, utils_s = line.split(":")
            items = [int(x) for x in items_s.split()]
            utils = [int(x) for x in utils_s.split()]
            tu = int(tu_s)
        except ValueError:
            raise ValueError(f"Line {lineno} is not in 'items:TU:utils' format: {raw_line!r}")
        if len(items) != len(utils):
            raise ValueError(f"Line {lineno}: {len(items)} items but {len(utils)} utilities")
        if sum(utils) != tu:
            raise ValueError(f"Line {lineno}: utilities sum to {sum(utils)}, but TU is {tu}")

        order = sorted(range(len(items)), key=lambda k: items[k])
        transactions.append({
            "tid": lineno,
            "items": [items[k] for k in order],
            "utils": [utils[k] for k in order],
            "TU": tu,
        })
    return transactions


def run_batch(batch_id, prefix_util, global_mru, item_lists,
              hashmap, batch_new, batch_old, k, capacity_K, stale_limit):
    """Runs Phase 3 -> Phase 4 -> Phase 5 for one batch."""
    if hashmap:
        min_util, watchlist_detail = compute_hdkt_threshold(
            hashmap, current_batch=batch_id, stale_limit=stale_limit, k=k,
            batch_new=batch_new, batch_old=batch_old)
    else:
        min_util, watchlist_detail = 0, []  # cold start, no history yet

    top_k, stats = mine_top_k(item_lists, prefix_util, global_mru, k=k, start_min_util=min_util)
    update_hashmap(hashmap, top_k, current_batch=batch_id, capacity_K=capacity_K)

    print(f"\n=== BATCH {batch_id} ({len(batch_new)} new txns"
          + (f", {len(batch_old)} evicted" if batch_old else "") + ") ===")
    print(f"HDkT current_min_util = {min_util}")
    for itemset, proj, u_new, u_old in watchlist_detail:
        print(f"  watchlist {itemset}: Projected_U={proj} (U_new={u_new}, U_old={u_old})")
    print(f"DFS stats: {stats}")
    print("Top-k this batch:")
    for util, iset in top_k:
        print(f"  {iset} util={util}")
    print("HashMap ranking after this batch:")
    for rank, (iset, e) in enumerate(rank_and_output(hashmap, top_n=capacity_K), start=1):
        print(f"  #{rank} {iset} avg_util={e['avg_util']:.1f} last_seen=batch{e['last_seen']}")


def stream_process(transactions, W, k, capacity_K, stale_limit, T_seconds=None):
    sw = SlidingWindow(W=W, T_seconds=T_seconds, evict_policy="whole_batch")
    prefix_util, global_mru, item_lists = {}, {}, {}
    hashmap = {}
    batch_id = 0

    for txn in transactions:
        sw.enqueue([txn])
        if sw.trigger_fired():
            batch, removed = sw.flush_batch()
            batch_id += 1
            if batch_id == 1:
                prefix_util, global_mru, item_lists = build_fresh(batch)
            else:
                add_batch(prefix_util, global_mru, item_lists, batch)
                remove_batch_prefix_util(prefix_util, item_lists, removed)
                global_mru = recompute_global_mru_fresh(sw.window)  # MAX aggregate: recompute
            run_batch(batch_id, prefix_util, global_mru, item_lists,
                      hashmap, batch_new=batch, batch_old=removed,
                      k=k, capacity_K=capacity_K, stale_limit=stale_limit)

    # end of stream: flush whatever is left in the queue as a final (possibly partial) batch
    if sw.queue:
        batch = sw.queue
        removed = sw.window
        sw.window = batch
        sw.queue = []
        batch_id += 1
        if batch_id == 1:
            prefix_util, global_mru, item_lists = build_fresh(batch)
        else:
            add_batch(prefix_util, global_mru, item_lists, batch)
            remove_batch_prefix_util(prefix_util, item_lists, removed)
            global_mru = recompute_global_mru_fresh(sw.window)
        print("\n[end of stream reached with a partial batch still queued -> flushing it now]")
        run_batch(batch_id, prefix_util, global_mru, item_lists,
                  hashmap, batch_new=batch, batch_old=removed,
                  k=k, capacity_K=capacity_K, stale_limit=stale_limit)

    if batch_id == 0:
        print("No transactions were provided — nothing to process.")

    return hashmap


def main():
    ap = argparse.ArgumentParser(description="Run the 5-phase streaming HUI-mining pipeline "
                                              "on user-supplied transactions.")
    ap.add_argument("--file", type=str, default=None,
                     help="Path to a transactions file. If omitted, reads from stdin.")
    ap.add_argument("--W", type=int, default=10, help="Window size / Condition 2 threshold (default: 10)")
    ap.add_argument("--k", type=int, default=5, help="Top-k itemsets to mine per batch (default: 5)")
    ap.add_argument("--capacity", type=int, default=10, help="HashMap capacity K for Phase 5 (default: 10)")
    ap.add_argument("--stale-limit", type=int, default=1,
                     help="Batches a pattern may go unseen before Phase 3 drops it (default: 1)")
    ap.add_argument("--time-threshold", type=float, default=None,
                     help="Optional Condition 1 time threshold in seconds (default: disabled)")
    args = ap.parse_args()

    if args.file:
        with open(args.file, "r") as f:
            lines = f.readlines()
    else:
        if sys.stdin.isatty():
            print("Paste your transactions (one per line, 'items:TU:utils' format).")
            print("Press Ctrl+D (Linux/Mac) or Ctrl+Z then Enter (Windows) when done.\n")
        lines = sys.stdin.readlines()

    transactions = parse_transactions(lines)
    if not transactions:
        print("No valid transactions found in input.")
        return

    stream_process(transactions, W=args.W, k=args.k, capacity_K=args.capacity,
                    stale_limit=args.stale_limit, T_seconds=args.time_threshold)


if __name__ == "__main__":
    main()