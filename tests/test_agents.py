from toolscale.agents import Agent
from toolscale.sim import Simulator
from toolscale.workers import WorkerPool


def times(agent):
    return [(r.arrival, r.start, r.finish) for r in agent.requests]


def test_single_agent_alternates_inference_and_tools():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=1, service_time=1.0)
    agent = Agent(sim, pool, agent_id=0, tool_durations=[2.0, 3.0])
    agent.start()
    sim.run()
    assert times(agent) == [(0.0, 0.0, 1.0), (3.0, 3.0, 4.0), (7.0, 7.0, 8.0)]
    assert [r.id for r in agent.requests] == ["0.0", "0.1", "0.2"]


def test_tools_finishing_together_cause_queueing():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=1, service_time=1.0)
    a = Agent(sim, pool, agent_id=0, tool_durations=[3.0])
    b = Agent(sim, pool, agent_id=1, tool_durations=[2.0])
    a.start()
    b.start()
    sim.run()
    assert times(a) == [(0.0, 0.0, 1.0), (4.0, 4.0, 5.0)]
    assert times(b) == [(0.0, 1.0, 2.0), (4.0, 5.0, 6.0)]
    post_tool_latency_b = b.requests[1].finish - b.requests[1].arrival
    assert post_tool_latency_b == 2.0  # 1s waiting behind a + 1s service


def test_agent_with_no_tools_makes_one_request():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=1, service_time=1.0)
    agent = Agent(sim, pool, agent_id=0, tool_durations=[])
    agent.start()
    sim.run()
    assert times(agent) == [(0.0, 0.0, 1.0)]
