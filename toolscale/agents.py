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
        warnings: list[float] | None = None,  # per tool: seconds of heads-up before it returns (0: none)
        on_tool_signal: Callable[[float], None] | None = None,  # called at a warning with the tool's return time
    ) -> None:
        self.sim = sim
        self.pool = pool
        self.agent_id = agent_id
        self.tool_durations = tool_durations
        self.requests: list[Request] = []
        self.on_finished = on_finished
        self.on_tool_start = on_tool_start
        self.warnings = warnings or []
        self.on_tool_signal = on_tool_signal

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
            return_time = self.sim.now + duration
            self.sim.schedule(duration, self._submit, name=f"tool_done_{req.id}")
            if self.on_tool_start:
                self.on_tool_start(return_time)
            warning = self.warnings[step] if step < len(self.warnings) else 0.0
            if warning >= duration and self.on_tool_signal:
                # A warning at least as long as the tool arrives with its start, before the pool's notice of the
                # finished inference runs the policy, as on_tool_start does. A zero-delay event would arrive after.
                self.on_tool_signal(return_time)
            elif warning > 0 and self.on_tool_signal:
                signal = self.on_tool_signal
                self.sim.schedule(duration - warning, lambda: signal(return_time), name=f"signal_{req.id}")
        elif self.on_finished:
            self.on_finished(self)
