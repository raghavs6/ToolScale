"""Compare fixed, reactive, and oracle capacity on one shared workload trace, at several wake delays.

Placeholder settings, not measurements of a real system. One seed only; multiple seeds and
uncertainty intervals come with the full experiment matrix (Milestone 4).
"""

import statistics

from toolscale.experiment import run_policy
from toolscale.policies.oracle import OraclePolicy
from toolscale.policies.reactive import ReactivePolicy
from toolscale.workloads import generate

SEED = 0
SERVICE_TIME = 2.0  # seconds per inference
# Real vLLM sleep-mode wakes take ~0.1-0.8s (small models) to ~3-6s (large); 20s is the original placeholder.
WAKE_DELAYS = (0.5, 5.0, 20.0)
MAX_WORKERS = 40  # dynamic policies' provisioned pool; ~12.5 workers are busy on average


def main() -> None:
    # Generated once, so every policy replays the identical workload.
    trace = generate(SEED, num_agents=200, tool_calls_per_agent=20, median=30.0, spread=0.5, start_window=300.0)
    starts = [a.start for a in trace]

    for wake_delay in WAKE_DELAYS:
        runs = []
        for n in range(8, 31, 2):
            runs.append((f"fixed N={n}", run_policy(trace, n, SERVICE_TIME, wake_delay)))
        # Short timeouts only pay off when wakes are fast; without them reactive is unfairly weak at 0.5s and 5s.
        for idle_timeout in (0.0, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0):
            name = f"reactive idle={idle_timeout:.0f}s"

            def make_policy(pool, idle_timeout=idle_timeout):
                return ReactivePolicy(pool, threshold=0, idle_timeout=idle_timeout)

            runs.append((name, run_policy(trace, MAX_WORKERS, SERVICE_TIME, wake_delay, make_policy)))
        runs.append(
            ("oracle", run_policy(trace, MAX_WORKERS, SERVICE_TIME, wake_delay, lambda pool: OraclePolicy(pool, starts)))
        )

        # Cost is active + waking: a policy that wakes often shouldn't look free. Mean wait leaves out the fixed 2s
        # of inference; p95 wait would just be p95 latency minus 2s.
        print(f"\nwake delay {wake_delay}s")
        print(
            f"{'policy':<22} {'p95 latency':>12} {'mean wait':>10} {'total worker-s':>15} {'active':>8} {'waking':>8}"
        )
        for name, r in sorted(runs, key=lambda run: run[1].active_seconds + run[1].waking_seconds):
            mean_wait = statistics.fmean(r.latencies) - SERVICE_TIME
            total = r.active_seconds + r.waking_seconds
            print(
                f"{name:<22} {r.p95:>11.2f}s {mean_wait:>9.3f}s {total:>15.0f} {r.active_seconds:>8.0f}"
                f" {r.waking_seconds:>8.0f}"
            )


if __name__ == "__main__":
    main()
