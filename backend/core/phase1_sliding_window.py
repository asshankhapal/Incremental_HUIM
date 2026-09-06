"""
PHASE 1: SLIDING WINDOW UPDATE (TRIGGER-BASED)
================================================
Flowchart boxes implemented here:
  - Trigger Evaluation (Parallel): Condition 1 (time elapsed >= T) OR Condition 2 (queued txns >= W)
  - Trigger Fired -> New Batch Arrives -> Identify Oldest Batch -> (utility-list update happens in Phase 2)

Design note: "Identify Oldest Batch / Remove outdated transactions from the window" is
implemented here as *whole-batch* eviction — the window holds at most one batch's worth
of transactions at a time, and an incoming batch evicts the previous one in full. This
matches the flowchart's wording of "oldest BATCH" (as opposed to oldest individual
transactions). If you need a strict per-transaction FIFO window instead, swap
`evict_policy="whole_batch"` for a transaction-count based eviction in `add_batch`.
"""

import time as _time

class SlidingWindow:
    def __init__(self, W, T_seconds=None, evict_policy="whole_batch"):
        """
        W            : transaction-count threshold for Condition 2
        T_seconds    : time threshold (seconds) for Condition 1. None disables Condition 1.
        evict_policy : "whole_batch" (evict entire previous batch) or "fifo" (evict oldest
                       individual transactions until len(window) <= W)
        """
        self.W = W
        self.T_seconds = T_seconds
        self.evict_policy = evict_policy
        self.queue = []              # transactions waiting to be flushed into a batch
        self.window = []             # transactions currently "in" the sliding window
        self.last_trigger_time = _time.time()
        self.batch_counter = 0

    # ---- Condition 1 & Condition 2 (parallel evaluation) -----------------
    def condition_1_time_elapsed(self, now=None):
        if self.T_seconds is None:
            return False
        now = now if now is not None else _time.time()
        return (now - self.last_trigger_time) >= self.T_seconds

    def condition_2_size_reached(self):
        return len(self.queue) >= self.W

    def trigger_fired(self, now=None):
        """OR logic: at least one condition true -> start pipeline."""
        return self.condition_1_time_elapsed(now) or self.condition_2_size_reached()

    # ---- Queueing new transactions ----------------------------------------
    def enqueue(self, transactions):
        """Transactions arrive continuously; they wait in queue until trigger fires."""
        self.queue.extend(transactions)

    # ---- Trigger Fired -> New Batch Arrives -> Identify Oldest Batch ------
    def flush_batch(self, now=None):
        """
        Call after trigger_fired() is True.
        Returns (new_batch, removed_batch) — the batch just added to the window,
        and the batch that was evicted from the window (or [] if nothing evicted).
        If neither condition is met, caller should NOT call this (batch stays queued).
        """
        if not self.trigger_fired(now):
            return None, None  # "batch waits in queue, re-evaluated on next arrival"

        self.batch_counter += 1
        new_batch = self.queue
        self.queue = []
        self.last_trigger_time = now if now is not None else _time.time()

        removed_batch = []
        if self.evict_policy == "whole_batch":
            removed_batch = self.window
            self.window = list(new_batch)
        else:  # "fifo"
            self.window.extend(new_batch)
            while len(self.window) > self.W:
                removed_batch.append(self.window.pop(0))

        return new_batch, removed_batch

if __name__ == "__main__":
    # quick smoke test
    sw = SlidingWindow(W=10, evict_policy="whole_batch")
    sw.enqueue(list(range(10)))
    print("trigger fired after 10 queued:", sw.trigger_fired())
    new_b, removed_b = sw.flush_batch()
    print("batch 1:", new_b, "| removed:", removed_b)

    sw.enqueue(list(range(10, 17)))
    print("trigger fired after 7 more queued (< W):", sw.trigger_fired())
    # simulate Condition 1 firing instead (time elapsed) by forcing it
    sw.T_seconds = 0
    new_b, removed_b = sw.flush_batch()
    print("batch 2:", new_b, "| removed:", removed_b)