"""Reactive policy: wakes sleeping workers based only on the current queue, with no forecast."""

from toolscale.workers import WorkerPool


class ReactivePolicy:
    def __init__(self, pool: WorkerPool, threshold: int) -> None:
        """Tolerate up to `threshold` waiting requests; beyond that, keep one worker on its way per extra request."""
        self.pool = pool
        self.threshold = threshold
        pool.on_change = self.decide

    def decide(self) -> None:
        # Waking workers count as help already on the way, so repeated notices in one burst don't over-wake.
        to_wake = len(self.pool.queue) - self.threshold - self.pool.waking
        if to_wake > 0:
            self.pool.wake(to_wake)
