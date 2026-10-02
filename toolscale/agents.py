"""Agents: each alternates inference requests and tool calls from a fixed script of tool durations."""

from toolscale.sim import Simulator
from toolscale.workers import Request, WorkerPool


class Agent:
    def __init__(self, sim: Simulator, pool: WorkerPool, agent_id: int, tool_durations: list[float]) -> None:
        self.sim = sim
        self.pool = pool
        self.agent_id = agent_id
        self.tool_durations = tool_durations
        self.requests: list[Request] = []

    def start(self) -> None:
        self._submit()

    def _submit(self) -> None:
        req = Request(id=f"{self.agent_id}.{len(self.requests)}", on_done=self._inference_done)
        self.requests.append(req)
        self.pool.submit(req)

    def _inference_done(self, req: Request) -> None:
        step = len(self.requests) - 1  # tool i follows inference i
        if step < len(self.tool_durations):
            self.sim.schedule(self.tool_durations[step], self._submit, name=f"tool_done_{req.id}")
