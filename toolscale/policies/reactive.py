"""Reactive policy: wakes sleeping workers based only on the current queue, with no forecast."""

from toolscale.workers import WorkerPool


class ReactivePolicy:
    def __init__(
        self, pool: WorkerPool, threshold: int, drain_aware: bool = False, idle_timeout: float | None = None
    ) -> None:
        """Tolerate up to `threshold` waiting requests; beyond that, keep one worker on its way per extra request.

        `drain_aware` skips waking when the active workers will clear the line before a woken worker could arrive.
        `idle_timeout` puts a worker to sleep once it has been idle that long (None: never sleep).
        """
        self.pool = pool
        self.threshold = threshold
        self.drain_aware = drain_aware
        self.idle_timeout = idle_timeout
        self._timer_pending = False
        pool.on_change = self.decide
        # Workers may already be idle; without this, nothing would time them out until the first pool notice.
        self.decide()

    def decide(self) -> None:
        # Never both in one call: requests only wait when no worker is idle.
        self._maybe_wake()
        self._maybe_sleep()

    def _maybe_wake(self) -> None:
        queue = len(self.pool.queue)
        # Line clears in about queue * service_time / active seconds; compared multiplied out so 0 active means
        # "never drains" instead of dividing by zero. Assumes fixed service times; random ones would need the mean.
        if self.drain_aware and queue * self.pool.service_time <= self.pool.wake_delay * self.pool.active:
            return
        # Waking workers count as help already on the way, so repeated notices in one burst don't over-wake.
        to_wake = queue - self.threshold - self.pool.waking
        if to_wake > 0:
            self.pool.wake(to_wake)

    def _maybe_sleep(self) -> None:
        if self.idle_timeout is None:
            return
        now, idle_since = self.pool.sim.now, self.pool.idle_since
        # idle_since is oldest first, so the timed-out workers are a block at the front.
        timed_out = 0
        while timed_out < len(idle_since) and idle_since[timed_out] + self.idle_timeout <= now:
            timed_out += 1
        self.pool.sleep(timed_out)
        # One timer, for the oldest idle worker's deadline. That deadline only moves later (LIFO reuses the newest
        # idle worker), so a pending timer is never late; if it fires early, decide() just sets the next one.
        if idle_since and not self._timer_pending:
            self._timer_pending = True
            deadline = idle_since[0] + self.idle_timeout
            self.pool.sim.schedule(deadline - now, self._timer_fired, name="policy_timer")

    def _timer_fired(self) -> None:
        self._timer_pending = False
        self.decide()
