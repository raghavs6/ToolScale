"""Run one policy on one workload trace and measure post-tool latency and capacity cost."""

import statistics
from dataclasses import dataclass
from typing import Callable

from toolscale.agents import Agent
from toolscale.sim import Simulator
from toolscale.workers import WorkerPool
from toolscale.workloads import AgentTrace


@dataclass
class Result:
    latencies: list[float]  # post-tool: finish - arrival for every request except each agent's first
    p95: float
    active_seconds: float  # worker-seconds from t=0 until the last request finished
    waking_seconds: float
    end: float  # when the last request finished


def run_policy(
    trace: list[AgentTrace],
    num_workers: int,
    service_time: float,
    wake_delay: float,
    make_policy: Callable[[WorkerPool], object] | None = None,
) -> Result:
    """Replay `trace` on a fresh pool with every worker awake. `make_policy(pool)` attaches a policy;
    None means fixed capacity (nobody ever wakes or sleeps)."""
    assert trace, "empty trace: the cost meter would never be read"
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=num_workers, service_time=service_time, wake_delay=wake_delay)
    if make_policy:
        make_policy(pool)

    # Stop the cost meter when the last agent finishes. The run itself may go on (idle workers waiting out
    # their timeout), but that tail isn't a cost of serving the workload.
    remaining = len(trace)
    active = waking = end = 0.0

    def finished(_: Agent) -> None:
        nonlocal remaining, active, waking, end
        remaining -= 1
        if remaining == 0:
            active, waking = pool.worker_seconds()
            end = sim.now

    agents = [Agent(sim, pool, i, a.tool_durations, on_finished=finished) for i, a in enumerate(trace)]
    for agent, a in zip(agents, trace):
        sim.schedule(a.start, agent.start, name="agent_start")
    sim.run()
    # A stranded agent would silently drop its latencies and make p95 look better than it is.
    assert remaining == 0, f"{remaining} agents never finished"

    latencies = [r.finish - r.arrival for agent in agents for r in agent.requests[1:]]
    # "inclusive" is the same interpolation as NumPy's default percentile.
    p95 = statistics.quantiles(latencies, n=100, method="inclusive")[94]
    return Result(latencies, p95, active, waking, end)
