"""Inference workers: a pool of identical workers (active, waking, or sleeping) serving a FIFO request queue."""

from collections import deque
from dataclasses import dataclass
from typing import Callable

from toolscale.sim import Simulator


@dataclass
class Request:
    id: str
    arrival: float | None = None
    start: float | None = None
    finish: float | None = None
    on_done: Callable[["Request"], None] | None = None  # called when service finishes


class WorkerPool:
    def __init__(
        self,
        sim: Simulator,
        num_workers: int,
        service_time: float,
        wake_delay: float = 0.0,
        initial_active: int | None = None,
    ) -> None:
        """`num_workers` counts all provisioned workers; `initial_active` of them start awake (default: all)."""
        self.sim = sim
        self.num_workers = num_workers
        self.service_time = service_time
        self.wake_delay = wake_delay
        self.active = num_workers if initial_active is None else initial_active
        self.waking = 0
        self.sleeping = num_workers - self.active
        self.busy = 0  # active workers currently serving a request
        self.queue: deque[Request] = deque()
        # Cost meter: worker-seconds spent active and waking, brought up to date at `_last_tick`.
        self.active_seconds = 0.0
        self.waking_seconds = 0.0
        self._last_tick = sim.now
        # Called (as a zero-delay event) when the pool changes on its own: arrival, finish, wake done.
        # Not on wake()/sleep(): the caller already knows, and notifying would let a policy loop on itself.
        self.on_change: Callable[[], None] | None = None
        self._check()

    def submit(self, req: Request) -> None:
        """A request arrives: serve it now if an active worker is free, else wait in line."""
        req.arrival = self.sim.now
        if self.busy < self.active:
            self.busy += 1
            self._start(req)
        else:
            self.queue.append(req)
        self._check()
        self._notify()

    def wake(self, n: int) -> None:
        """Start waking up to `n` sleeping workers; each becomes active after `wake_delay`."""
        n = min(n, self.sleeping)
        self._tick()
        self.sleeping -= n
        self.waking += n
        for _ in range(n):
            self.sim.schedule(self.wake_delay, self._wake_done, name="wake_done")
        self._check()

    def sleep(self, n: int) -> None:
        """Put up to `n` idle active workers to sleep, instantly. Busy and waking workers are skipped."""
        n = min(n, self.active - self.busy)
        self._tick()
        self.active -= n
        self.sleeping += n
        self._check()

    def worker_seconds(self) -> tuple[float, float]:
        """(active, waking) worker-seconds from creation up to now. Busy and idle active workers cost the same."""
        self._tick()
        return self.active_seconds, self.waking_seconds

    def _tick(self) -> None:
        """Add cost since the last tick. Call before every change to `active` or `waking`."""
        elapsed = self.sim.now - self._last_tick
        self.active_seconds += self.active * elapsed
        self.waking_seconds += self.waking * elapsed
        self._last_tick = self.sim.now

    def _wake_done(self) -> None:
        self._tick()
        self.waking -= 1
        self.active += 1
        if self.queue:
            # Serve the line immediately, so no request waits while this worker sits idle.
            self.busy += 1
            self._start(self.queue.popleft())
        self._check()
        self._notify()

    def _check(self) -> None:
        """Invariants that must hold after every state change; fail loudly the moment one breaks."""
        assert min(self.active, self.waking, self.sleeping) >= 0, "negative worker count"
        assert self.active + self.waking + self.sleeping == self.num_workers, "workers appeared or vanished"
        assert 0 <= self.busy <= self.active, f"busy={self.busy} out of range"
        assert not self.queue or self.busy == self.active, "request waiting while a worker is idle"

    def _notify(self) -> None:
        """Schedule `on_change` rather than call it, so the listener runs after this change (and any
        others at the same instant) has finished, never in the middle of a pool method."""
        if self.on_change:
            self.sim.schedule(0.0, self.on_change, name="pool_change")

    def _start(self, req: Request) -> None:
        req.start = self.sim.now
        self.sim.schedule(self.service_time, lambda: self._finish(req), name=f"finish_{req.id}")

    def _finish(self, req: Request) -> None:
        req.finish = self.sim.now
        if self.queue:
            # Hand the worker straight to the next in line, so a same-time arrival can't cut ahead.
            self._start(self.queue.popleft())
        else:
            self.busy -= 1
        self._check()
        self._notify()
        if req.on_done:
            req.on_done(req)
