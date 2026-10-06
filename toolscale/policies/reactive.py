"""Reactive policy: wakes sleeping workers based only on the current queue, with no forecast."""

from toolscale.workers import WorkerPool


class ReactivePolicy:
    def __init__(self, pool: WorkerPool, threshold: int, drain_aware: bool = False) -> None:
        """Tolerate up to `threshold` waiting requests; beyond that, keep one worker on its way per extra request.

        `drain_aware` skips waking when the active workers will clear the line before a woken worker could arrive.
        """
        self.pool = pool
        self.threshold = threshold
        self.drain_aware = drain_aware
        pool.on_change = self.decide

    def decide(self) -> None:
        queue = len(self.pool.queue)
        # Line clears in about queue * service_time / active seconds; compared multiplied out so 0 active means
        # "never drains" instead of dividing by zero. Assumes fixed service times; random ones would need the mean.
        if self.drain_aware and queue * self.pool.service_time <= self.pool.wake_delay * self.pool.active:
            return
        # Waking workers count as help already on the way, so repeated notices in one burst don't over-wake.
        to_wake = queue - self.threshold - self.pool.waking
        if to_wake > 0:
            self.pool.wake(to_wake)
