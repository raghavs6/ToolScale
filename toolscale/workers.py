"""Inference workers: a pool of identical always-on workers serving a FIFO request queue."""

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
    def __init__(self, sim: Simulator, num_workers: int, service_time: float) -> None:
        self.sim = sim
        self.num_workers = num_workers
        self.service_time = service_time
        self.busy = 0
        self.queue: deque[Request] = deque()

    def submit(self, req: Request) -> None:
        """A request arrives: serve it now if a worker is free, else wait in line."""
        req.arrival = self.sim.now
        if self.busy < self.num_workers:
            self.busy += 1
            self._start(req)
        else:
            self.queue.append(req)
        self._check()

    def _check(self) -> None:
        """Invariants that must hold after every state change; fail loudly the moment one breaks."""
        assert 0 <= self.busy <= self.num_workers, f"busy={self.busy} out of range"
        assert not self.queue or self.busy == self.num_workers, "request waiting while a worker is idle"

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
        if req.on_done:
            req.on_done(req)
