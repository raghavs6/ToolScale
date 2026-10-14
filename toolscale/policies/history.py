"""History-based policy: forecasts tool returns from how long each tool has run and past durations, without progress."""

import bisect
import math

from toolscale.forecasting import expected_returns
from toolscale.workers import WorkerPool


class HistoryPolicy:
    def __init__(
        self, pool: WorkerPool, past_durations: list[float], starts: list[float], headroom: int, idle_timeout: float
    ) -> None:
        """Keep enough workers awake or on the way for the expected demand when a wake started now would land.

        Same shape as the oracle (wake when active + waking falls short of `required`, sleep idle workers above
        it), so the two differ only in their forecast. `past_durations` come from other runs, never this one.
        `starts` are the agents' first requests, from the trace, as the oracle gets them. `headroom` adds spare
        workers on top of the expected demand, which is an average; sweeping it traces a cost-latency curve.
        `idle_timeout` lets a surplus worker sleep only once it has been idle that long. The forecast is noisy, so
        without it the policy sleeps workers it re-wakes moments later, paying a full wake delay each time.
        """
        self.pool = pool
        self.past = sorted(past_durations)
        self.starts = sorted(starts)
        self.headroom = headroom
        self.idle_timeout = idle_timeout
        # (start, return_time) per running tool. The return time is used only to drop a tool once it has
        # returned, which the policy sees then anyway as an arriving request; the forecast uses the start alone.
        self.running: list[tuple[float, float]] = []
        # Forecasts age as tools run on, even when no event happens; re-check this often while any tool runs.
        self.tick = min(pool.wake_delay, pool.service_time) / 2
        self._tick_pending = False
        pool.on_change = self.decide
        self.decide()

    def tool_started(self, return_time: float) -> None:
        self.running.append((self.pool.sim.now, return_time))

    def decide(self) -> None:
        pool, now = self.pool, self.pool.sim.now
        self.running = [(start, ret) for start, ret in self.running if ret > now]
        required = math.ceil(self._expected_peak(now) - 1e-9) + self.headroom  # 1e-9: sums of fractions drift
        to_wake = required - pool.active - pool.waking
        if to_wake > 0:
            pool.wake(to_wake)
        elif pool.active > required:
            # idle_since is oldest first, so the timed-out workers are a block at the front.
            timed_out = 0
            while timed_out < len(pool.idle_since) and pool.idle_since[timed_out] + self.idle_timeout <= now:
                timed_out += 1
            pool.sleep(min(pool.active - required, timed_out))
        if self.running and not self._tick_pending:
            self._tick_pending = True
            pool.sim.schedule(self.tick, self._tick_fired, name="history_tick")

    def _tick_fired(self) -> None:
        self._tick_pending = False
        self.decide()

    def _expected_peak(self, now: float) -> float:
        """Largest expected demand from now until a wake started now would land.

        Checked now and at evenly spaced instants about one service time apart, ending at the landing time.
        Checking only the landing time was tried first and slept workers needed in between, which then had to be
        re-woken: at a 20s wake delay that cost more than reactive at every headroom.
        """
        pool = self.pool
        s, w = pool.service_time, pool.wake_delay
        elapsed = [now - start for start, _ in self.running]
        peak = float(pool.busy + len(pool.queue))
        steps = max(1, round(w / s))
        for j in range(1, steps + 1):
            ahead = w * j / steps
            t = now + ahead
            still_busy = sum(1 for r in pool.serving if r.start + s > t)
            starting = bisect.bisect_right(self.starts, t) - bisect.bisect_right(self.starts, max(t - s, now))
            peak = max(peak, still_busy + len(pool.queue) + starting + self._returning(elapsed, ahead, t))
        return peak

    def _returning(self, elapsed: list[float], ahead: float, t: float) -> float:
        """Expected requests from running tools arriving in the service time before t, which is `ahead` from now."""
        return expected_returns(elapsed, self.past, ahead - self.pool.service_time, ahead)
