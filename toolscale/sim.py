"""Discrete-event simulation engine: a clock plus a time-ordered queue of callbacks."""

import heapq
from typing import Callable


class Simulator:
    def __init__(self) -> None:
        self.now = 0.0
        self.log: list[tuple[float, str]] = []  # (time, name) of every event that ran
        self._queue: list[tuple[float, int, str, Callable[[], None]]] = []
        self._seq = 0  # tie-breaker: equal-time events run in schedule order

    def schedule(self, delay: float, fn: Callable[[], None], name: str) -> None:
        """Run `fn` after `delay` simulated seconds."""
        if delay < 0:
            raise ValueError(f"cannot schedule {name!r} in the past (delay={delay})")
        heapq.heappush(self._queue, (self.now + delay, self._seq, name, fn))
        self._seq += 1

    def run(self, until: float | None = None) -> None:
        """Process events in time order until the queue empties or the next event is after `until`.

        Events at exactly `until` run. If `until` is given, the clock ends at `until`.
        """
        while self._queue:
            if until is not None and self._queue[0][0] > until:
                break
            time, _, name, fn = heapq.heappop(self._queue)
            self.now = time
            self.log.append((time, name))
            fn()
        if until is not None:
            self.now = until
