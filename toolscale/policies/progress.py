"""Progress-aware policy: the history policy, plus exact return times from tools that send a heads-up."""

import bisect

from toolscale.policies.history import HistoryPolicy


class ProgressPolicy(HistoryPolicy):
    """When a tool warns, stop guessing its return from history and count it exactly, as the oracle does.

    Silent tools keep the history forecast. A tool's return time is learned only at its warning, never at its start.
    """

    def __init__(self, *args, **kwargs) -> None:
        self.known: list[float] = []  # return times of warned tools, sorted; set before the first decide()
        super().__init__(*args, **kwargs)

    def tool_signaled(self, return_time: float) -> None:
        # The tool moves from the history guess to the exact count. Its running entry is found by return time,
        # which the policy holds only to drop finished tools (see HistoryPolicy).
        index = next(i for i, (_, ret) in enumerate(self.running) if ret == return_time)
        del self.running[index]
        bisect.insort(self.known, return_time)
        # The last moment a wake still lands on time; if that has passed, the decide below wakes at once.
        wake_at = return_time - self.pool.wake_delay
        if wake_at > self.pool.sim.now:
            self.pool.sim.schedule(wake_at - self.pool.sim.now, self.decide, name="progress_wake")
        self.decide()

    def decide(self) -> None:
        # A known return at or before now has already arrived as a request, so the queue or pool counts it.
        del self.known[: bisect.bisect_right(self.known, self.pool.sim.now)]
        super().decide()

    def _check_aheads(self, now: float) -> list[float]:
        # Demand peaks at returns. History's evenly spaced checks suit its smooth guess but can fall between two
        # known returns, so also check at each one before the landing time, as the oracle does.
        end = bisect.bisect_right(self.known, now + self.pool.wake_delay)
        return super()._check_aheads(now) + [ret - now for ret in self.known[:end]]

    def _returning(self, elapsed: list[float], ahead: float, t: float) -> float:
        known = bisect.bisect_right(self.known, t) - bisect.bisect_right(self.known, t - self.pool.service_time)
        return super()._returning(elapsed, ahead, t) + known
