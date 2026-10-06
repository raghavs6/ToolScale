"""Synthetic workloads: seeded traces of agents, drawn up front so every policy replays the identical workload."""

import math
import random
from dataclasses import dataclass


@dataclass
class AgentTrace:
    start: float  # when the agent sends its first inference request
    tool_durations: list[float]


def generate(
    seed: int, num_agents: int, tool_calls_per_agent: int, median: float, spread: float, start_window: float
) -> list[AgentTrace]:
    """Agents start uniformly in [0, start_window]; tool durations are lognormal with the given median.

    `spread` is the lognormal sigma: 0 makes every tool take exactly `median`; larger values add a long tail.
    Draw order (changing it changes every trace for a seed): per agent, its start, then its tool durations.
    """
    rng = random.Random(seed)  # private, so no other code can shift the sequence
    trace = []
    for _ in range(num_agents):
        start = rng.uniform(0.0, start_window)
        # median * e^(spread * z) is lognormal; unlike rng.lognormvariate(log(median), 0) it returns
        # exactly `median` when spread is 0.
        durations = [median * math.exp(spread * rng.gauss(0.0, 1.0)) for _ in range(tool_calls_per_agent)]
        trace.append(AgentTrace(start, durations))
    return trace
