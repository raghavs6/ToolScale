"""First comparison: fixed vs reactive capacity on one shared workload trace.

Placeholder settings, not measurements of a real system. One seed only; multiple seeds and
uncertainty intervals come with the full experiment matrix (Milestone 4).
"""

from toolscale.experiment import run_policy
from toolscale.policies.reactive import ReactivePolicy
from toolscale.workloads import generate

SEED = 0
SERVICE_TIME = 2.0  # seconds per inference
WAKE_DELAY = 20.0  # comparable to tool times: the regime where waking early could matter
MAX_WORKERS = 40  # reactive's provisioned pool; ~12.5 workers are busy on average


def main() -> None:
    # Generated once, so every policy replays the identical workload.
    trace = generate(SEED, num_agents=200, tool_calls_per_agent=20, median=30.0, spread=0.5, start_window=300.0)

    runs = []
    for n in range(8, 31, 2):
        runs.append((f"fixed N={n}", run_policy(trace, n, SERVICE_TIME, WAKE_DELAY)))
    for drain_aware in (False, True):
        for idle_timeout in (10.0, 30.0, 60.0, 120.0, 300.0):
            name = f"reactive {'drain' if drain_aware else 'simple'} idle={idle_timeout:.0f}s"

            def make_policy(pool, drain_aware=drain_aware, idle_timeout=idle_timeout):
                return ReactivePolicy(pool, threshold=0, drain_aware=drain_aware, idle_timeout=idle_timeout)

            runs.append((name, run_policy(trace, MAX_WORKERS, SERVICE_TIME, WAKE_DELAY, make_policy)))

    print(f"{'policy':<28} {'p95 latency':>12} {'active worker-s':>16} {'waking worker-s':>16} {'last finish':>12}")
    for name, r in sorted(runs, key=lambda run: run[1].active_seconds):
        print(f"{name:<28} {r.p95:>11.2f}s {r.active_seconds:>16.0f} {r.waking_seconds:>16.0f} {r.end:>11.0f}s")


if __name__ == "__main__":
    main()
