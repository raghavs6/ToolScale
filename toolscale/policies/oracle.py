"""Oracle policy: told each tool's exact return time when the tool starts. A ceiling for progress-aware, not a baseline."""

import bisect

from toolscale.workers import WorkerPool


class OraclePolicy:
    def __init__(self, pool: WorkerPool, starts: list[float]) -> None:
        """Keep exactly enough workers awake or on the way to cover the peak demand within one wake delay.

        One number drives both directions: wake when active + waking falls short of it; sleep idle workers above it.
        A worker not needed within one wake delay can sleep and be re-woken in time, for no more than staying up.
        `starts` are the agents' first requests, from the trace; later requests are announced by tool_started().
        """
        self.pool = pool
        # Known return times still in the future, sorted.
        self.returns: list[float] = []
        pool.on_change = self.decide
        for start in starts:
            self.tool_started(start)
        self.decide()

    def tool_started(self, return_time: float) -> None:
        """Called by agents (via run_policy) as each tool starts, and by __init__ for each agent's first request."""
        bisect.insort(self.returns, return_time)
        # The last moment a wake can still land in time. If that has passed, the pool notice already queued
        # behind this call runs decide().
        lead = return_time - self.pool.wake_delay - self.pool.sim.now
        if lead > 0:
            self.pool.sim.schedule(lead, self.decide, name="oracle_timer")

    def decide(self) -> None:
        pool, now = self.pool, self.pool.sim.now
        while self.returns and self.returns[0] <= now:  # arrived: now counted in busy or the queue
            self.returns.pop(0)
        required = self._peak_demand(now, now + pool.wake_delay)
        to_wake = required - pool.active - pool.waking
        if to_wake > 0:
            pool.wake(to_wake)
        elif pool.active > required:
            pool.sleep(pool.active - required)  # skips busy workers

    def _peak_demand(self, now: float, end: float) -> int:
        """Most workers needed at any instant in [now, end], if nobody else waits.

        Demand only rises at a return, so the peak is now or at one of the returns in (now, end]. Each return holds
        a worker for one service time. Requests already in service hold theirs until their real finish, which is
        later than planned if they waited; the queue is counted throughout.
        """
        pool = self.pool
        finishes = sorted(r.start + pool.service_time for r in pool.serving)
        peak = pool.busy + len(pool.queue)
        for i, t in enumerate(self.returns):
            if t > end:
                break
            # returns[:i + 1] are the ones up to t; drop those finished by t, if served at once.
            arriving = i + 1 - bisect.bisect_right(self.returns, t - pool.service_time)
            still_busy = len(finishes) - bisect.bisect_right(finishes, t)
            peak = max(peak, arriving + still_busy + len(pool.queue))
        return peak
