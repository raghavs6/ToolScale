from toolscale.experiment import run_policy
from toolscale.policies.reactive import ReactivePolicy
from toolscale.workloads import AgentTrace, generate

# Both agents return from their tools at t=4 and collide.
COLLIDE = [AgentTrace(start=0.0, tool_durations=[3.0]), AgentTrace(start=0.0, tool_durations=[2.0])]


def test_fixed_hand_example():
    result = run_policy(COLLIDE, num_workers=1, service_time=1.0, wake_delay=5.0)
    # First requests (startup) are excluded; A is served 4-5, B waits behind it and is served 5-6.
    assert result.latencies == [1.0, 2.0]
    assert result.p95 == 1.95
    assert result.end == 6.0
    assert result.active_seconds == 1 * 6.0


def test_cost_meter_stops_at_last_finish():
    # The last request finishes at t=5, but idle workers keep billing until they time out near t=105.
    result = run_policy(
        COLLIDE,
        num_workers=2,
        service_time=1.0,
        wake_delay=5.0,
        make_policy=lambda pool: ReactivePolicy(pool, threshold=0, idle_timeout=100.0),
    )
    assert result.end == 5.0
    assert result.active_seconds == 2 * 5.0


def test_same_trace_same_result():
    trace = generate(seed=0, num_agents=20, tool_calls_per_agent=5, median=30.0, spread=0.5, start_window=60.0)

    def run():
        return run_policy(
            trace,
            num_workers=4,
            service_time=2.0,
            wake_delay=20.0,
            make_policy=lambda pool: ReactivePolicy(pool, threshold=0, idle_timeout=30.0),
        )

    assert run() == run()
