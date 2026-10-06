import statistics

import pytest

from toolscale.agents import Agent
from toolscale.sim import Simulator
from toolscale.workers import WorkerPool
from toolscale.workloads import generate

SETTINGS = dict(num_agents=5, tool_calls_per_agent=4, median=30.0, spread=1.0, start_window=10.0)


def test_same_seed_same_trace():
    assert generate(seed=1, **SETTINGS) == generate(seed=1, **SETTINGS)
    assert generate(seed=1, **SETTINGS) != generate(seed=2, **SETTINGS)


def test_zero_spread_and_window_is_hand_checkable():
    trace = generate(seed=1, num_agents=3, tool_calls_per_agent=2, median=7.0, spread=0.0, start_window=0.0)
    assert [(a.start, a.tool_durations) for a in trace] == [(0.0, [7.0, 7.0])] * 3


def test_durations_are_lognormal_around_median():
    trace = generate(seed=1, num_agents=100, tool_calls_per_agent=100, median=30.0, spread=1.0, start_window=0.0)
    durations = [d for a in trace for d in a.tool_durations]
    assert min(durations) > 0
    assert statistics.median(durations) == pytest.approx(30.0, rel=0.05)
    assert max(durations) > 10 * 30.0  # a long tail: a few tools take far longer than typical


def test_same_trace_gives_same_tool_durations_under_any_capacity():
    # Short tools vs 1s service, so queueing reorders agents (the case where drawing randomness
    # mid-simulation handed different policies different durations).
    trace = generate(seed=42, num_agents=3, tool_calls_per_agent=3, median=1.5, spread=0.5, start_window=0.0)

    def run(num_workers):
        sim = Simulator()
        pool = WorkerPool(sim, num_workers=num_workers, service_time=1.0)
        agents = [Agent(sim, pool, i, a.tool_durations) for i, a in enumerate(trace)]
        for agent, a in zip(agents, trace):
            sim.schedule(a.start, agent.start, name="agent_start")
        sim.run()
        finishes = [[r.finish for r in agent.requests] for agent in agents]
        tools = [[nxt.arrival - req.finish for req, nxt in zip(agent.requests, agent.requests[1:])] for agent in agents]
        return finishes, tools

    finishes_1, tools_1 = run(1)
    finishes_3, tools_3 = run(3)
    assert finishes_1 != finishes_3  # the runs really did diverge in timing...
    for got_1, got_3, a in zip(tools_1, tools_3, trace):
        assert got_1 == pytest.approx(a.tool_durations)  # ...yet each agent's tools took the same time
        assert got_3 == pytest.approx(a.tool_durations)
