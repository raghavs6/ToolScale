"""Agents: each alternates inference requests and tool calls from a fixed script of tool durations."""

from typing import Callable

from toolscale.sim import Simulator
from toolscale.workers import Request, WorkerPool


class Agent:
    def __init__(
        self,
        sim: Simulator,
        pool: WorkerPool,
        agent_id: int,
        tool_durations: list[float],
        on_finished: Callable[["Agent"], None] | None = None,  # called when the last inference finishes
        on_tool_start: Callable[[float], None] | None = None,  # called with the time a starting tool will return
    ) -> None:
        self.sim = sim
        self.pool = pool
        self.agent_id = agent_id
        self.tool_durations = tool_durations
        self.requests: list[Request] = []
        self.on_finished = on_finished
        self.on_tool_start = on_tool_start

    def start(self) -> None:
        self._submit()

    def _submit(self) -> None:
        req = Request(id=f"{self.agent_id}.{len(self.requests)}", on_done=self._inference_done)
        self.requests.append(req)
        self.pool.submit(req)

    def _inference_done(self, req: Request) -> None:
        step = len(self.requests) - 1  # tool i follows inference i
        if step < len(self.tool_durations):
            duration = self.tool_durations[step]
            self.sim.schedule(duration, self._submit, name=f"tool_done_{req.id}")
            if self.on_tool_start:
                self.on_tool_start(self.sim.now + duration)
        elif self.on_finished:
            self.on_finished(self)
