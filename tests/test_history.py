from toolscale.experiment import run_policy
from toolscale.policies.history import HistoryPolicy
from toolscale.workloads import AgentTrace

# Service 2s, wake 5s: the policy re-checks every min(5, 2) / 2 = 1s while a tool runs.


def run(trace, past, headroom=0, idle_timeout=0.0, policy=HistoryPolicy):
    def make_policy(pool):
        return policy(pool, past, [a.start for a in trace], headroom, idle_timeout)

    return run_policy(trace, 2, service_time=2.0, wake_delay=5.0, make_policy=make_policy)


def test_wakes_ahead_when_history_says_a_return_is_due():
    # Every past tool took 30s. The first request is served 5-7, so the tool runs 7-37 and the worker sleeps.
    # At t=32 (25s in) the window a wake would land in, 28-30s of runtime, holds the 30s duration: wake, land at 37.
    result = run([AgentTrace(start=0.0, tool_durations=[30.0])], past=[30.0])
    assert result.latencies == [2.0]
    assert result.active_seconds == 2.0 + 2.0  # 5-7 and 37-39
    assert result.waking_seconds == 5.0 + 5.0  # 0-5 and 32-37


def test_headroom_keeps_spare_workers():
    # One spare: at t=0 a worker wakes for headroom alone, and the arriving first request wakes a second.
    # The spare stays up through the tool and serves the return; the second sleeps at 7 and re-wakes at 32.
    result = run([AgentTrace(start=0.0, tool_durations=[30.0])], past=[30.0], headroom=1)
    assert result.latencies == [2.0]
    assert result.active_seconds == 2 * 2.0 + 30.0 + 2 * 2.0  # 5-7 both, 7-37 the spare, 37-39 both
    assert result.waking_seconds == 3 * 5.0


def test_idle_timeout_delays_sleep():
    # Same as the first test, but the idle worker may only sleep once idle 10s: it goes idle at 7 and sleeps at
    # the re-check at 17, then is re-woken at 32 as before.
    result = run([AgentTrace(start=0.0, tool_durations=[30.0])], past=[30.0], idle_timeout=10.0)
    assert result.latencies == [2.0]
    assert result.active_seconds == (17.0 - 5.0) + 2.0  # 5-17 and 37-39
    assert result.waking_seconds == 5.0 + 5.0


def test_does_not_peek_at_return_times():
    # Same history, tools that actually take 30s vs 40s: until the first returns (t=37), the policy must act
    # identically, because nothing it is allowed to see differs.
    def decisions(duration):
        seen = []

        class Recorded(HistoryPolicy):
            def decide(self):
                super().decide()
                seen.append((self.pool.sim.now, self.pool.active, self.pool.waking))

        run([AgentTrace(start=0.0, tool_durations=[duration])], past=[30.0, 40.0], policy=Recorded)
        return [d for d in seen if d[0] < 37.0]

    assert decisions(30.0) == decisions(40.0)
    assert len(decisions(30.0)) > 30  # it really was deciding throughout, tick by tick
