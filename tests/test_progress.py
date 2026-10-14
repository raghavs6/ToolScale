from toolscale.experiment import run_policy
from toolscale.policies.history import HistoryPolicy
from toolscale.policies.progress import ProgressPolicy
from toolscale.workloads import AgentTrace, generate

# Service 2s, wake 5s, as in test_history.py. History says tools take 60s, so without a warning a 30s tool
# returns unforeseen. The first request is served 5-7, so the tool runs 7-37.


def run(trace, past=(60.0,), policy=ProgressPolicy, num_workers=2):
    def make_policy(pool):
        return policy(pool, list(past), [a.start for a in trace], 0, 0.0)

    return run_policy(trace, num_workers, service_time=2.0, wake_delay=5.0, make_policy=make_policy)


def test_without_warnings_matches_history_exactly():
    trace = generate(seed=0, num_agents=20, tool_calls_per_agent=5, median=30.0, spread=0.5, start_window=60.0)
    past = [a for agent in generate(1, 20, 5, 30.0, 0.5, 60.0) for a in agent.tool_durations]
    assert run(trace, past, ProgressPolicy, 10) == run(trace, past, HistoryPolicy, 10)


def test_a_warning_longer_than_the_wake_delay_lands_a_worker_on_time():
    # The tool warns at 37-10=27. The policy waits until 37-5=32 to wake, and the worker lands as the request does.
    result = run([AgentTrace(start=0.0, tool_durations=[30.0], warnings=[10.0])])
    assert result.latencies == [2.0]
    assert result.active_seconds == 2.0 + 2.0  # 5-7 and 37-39
    assert result.waking_seconds == 5.0 + 5.0  # 0-5 and 32-37


def test_a_warning_shorter_than_the_wake_delay_saves_part_of_the_wait():
    # The tool warns at 35, too late to land by 37: the wake starts at once and lands at 40, 3s after the return.
    # Without the warning, history waits for the request itself: it wakes at 37 and lands at 42.
    warned = run([AgentTrace(start=0.0, tool_durations=[30.0], warnings=[2.0])])
    silent = run([AgentTrace(start=0.0, tool_durations=[30.0])])
    assert warned.latencies == [3.0 + 2.0]
    assert silent.latencies == [5.0 + 2.0]


def test_does_not_peek_before_the_warning():
    # Tools of 30s and 40s, each warning 5s ahead: the first warning is at 37-5=32, so until then the policy must act
    # identically, because nothing it is allowed to see differs.
    def decisions(duration):
        seen = []

        class Recorded(ProgressPolicy):
            def decide(self):
                super().decide()
                seen.append((self.pool.sim.now, self.pool.active, self.pool.waking))

        run([AgentTrace(start=0.0, tool_durations=[duration], warnings=[5.0])], past=[30.0, 40.0], policy=Recorded)
        return [d for d in seen if d[0] < 32.0]

    assert decisions(30.0) == decisions(40.0)
    assert len(decisions(30.0)) > 25  # it really was deciding throughout, tick by tick


def test_keeps_a_worker_for_a_known_return_between_check_times():
    # The second tool runs 19-21.7 and warns at its start. History checks demand only at 19+2.5 and 19+5, each
    # covering the 2s before it, and 21.7 falls between those windows. The known return must still keep the idle
    # worker awake: sleeping it at 19 would make the request at 21.7 wait for a wake.
    result = run([AgentTrace(start=0.0, tool_durations=[10.0, 2.7], warnings=[10.0, 2.7])])
    assert result.latencies == [2.0, 2.0]
