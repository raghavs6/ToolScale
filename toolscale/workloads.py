"""Synthetic workloads: seeded traces of agents, drawn up front so every policy replays the identical workload."""

import math
import random
from dataclasses import dataclass, field


@dataclass
class AgentTrace:
    start: float  # when the agent sends its first inference request
    tool_durations: list[float]
    # Seconds of heads-up each tool gives before it returns (0: none). Empty: no tool warns.
    warnings: list[float] = field(default_factory=list)


def generate(
    seed: int,
    num_agents: int,
    tool_calls_per_agent: int,
    median: float,
    spread: float,
    start_window: float,
    warn_share: float = 0.0,
    warning: float = 0.0,
) -> list[AgentTrace]:
    """Agents start uniformly in [0, start_window]; tool durations are lognormal with the given median.

    `spread` is the lognormal sigma: 0 makes every tool take exactly `median`; larger values add a long tail.
    Draw order (changing it changes every trace for a seed): per agent, its start, then its tool durations.

    Each tool, with probability `warn_share`, announces its return `warning` seconds ahead (a model of live
    progress). Those draws use their own stream, so adding warnings leaves starts and durations unchanged.
    """
    rng = random.Random(seed)  # private, so no other code can shift the sequence
    trace = []
    for _ in range(num_agents):
        start = rng.uniform(0.0, start_window)
        # median * e^(spread * z) is lognormal; unlike rng.lognormvariate(log(median), 0) it returns
        # exactly `median` when spread is 0.
        durations = [median * math.exp(spread * rng.gauss(0.0, 1.0)) for _ in range(tool_calls_per_agent)]
        trace.append(AgentTrace(start, durations))
    if warn_share > 0:
        warn_rng = random.Random(f"warnings-{seed}")  # a str seed is hashed deterministically, unlike hash()
        for agent in trace:
            agent.warnings = [warning if warn_rng.random() < warn_share else 0.0 for _ in agent.tool_durations]
    return trace
