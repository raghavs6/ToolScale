from toolscale.experiment import run_policy
from toolscale.policies.oracle import OraclePolicy
from toolscale.workloads import AgentTrace

# Service 2s, wake 20s throughout, like experiments/run.py.


def run(trace, num_workers=1):
    return run_policy(trace, num_workers, service_time=2.0, wake_delay=20.0, make_policy=lambda pool: OraclePolicy(pool, [a.start for a in trace]))


def test_sleeps_through_a_long_tool_and_wakes_just_in_time():
    # Cold start: the first request waits for a wake (0-20) and is served 20-22. The 30s tool returns at 52.
    # The worker isn't needed within 20s of t=22, so it sleeps, is re-woken at 52-20=32, and lands at 52.
    result = run([AgentTrace(start=0.0, tool_durations=[30.0])])
    assert result.latencies == [2.0]
    assert result.active_seconds == 2.0 + 2.0  # 20-22 and 52-54
    assert result.waking_seconds == 20.0 + 20.0  # 0-20 and 32-52


def test_stays_awake_through_a_tool_shorter_than_the_wake_delay():
    # The 10s tool returns at 32, within 20s of t=22, so the worker stays up rather than sleeping.
    result = run([AgentTrace(start=0.0, tool_durations=[10.0])])
    assert result.latencies == [2.0]
    assert result.active_seconds == 34.0 - 20.0
    assert result.waking_seconds == 20.0


def test_has_one_worker_ready_per_simultaneous_return():
    # Both first requests are served 20-22; both 30s tools return at 52, so two workers land at 52.
    trace = [AgentTrace(start=0.0, tool_durations=[30.0]), AgentTrace(start=0.0, tool_durations=[30.0])]
    result = run(trace, num_workers=2)
    assert result.latencies == [2.0, 2.0]
    assert result.active_seconds == 2 * (2.0 + 2.0)


def test_returns_two_seconds_apart_share_one_worker():
    # Tools return at 52 and 54: the first request finishes as the second arrives, so one worker serves both.
    trace = [AgentTrace(start=0.0, tool_durations=[30.0]), AgentTrace(start=0.0, tool_durations=[32.0])]
    result = run(trace, num_workers=2)
    assert result.latencies == [2.0, 2.0]
    assert result.active_seconds == 2 * 2.0 + 4.0  # both 20-22, then one worker 52-56
