"""Compare fixed, reactive, history, and oracle capacity on one shared workload trace, at several wake delays.

Placeholder settings, not measurements of a real system. One seed here; `seeds.py` checks the verdicts across
seeds. Uncertainty intervals come with the full experiment matrix (Milestone 4).
"""

import statistics

from toolscale.experiment import Result, run_policy
from toolscale.policies.history import HistoryPolicy
from toolscale.policies.oracle import OraclePolicy
from toolscale.policies.reactive import ReactivePolicy
from toolscale.workloads import AgentTrace, generate

SEED = 0
SERVICE_TIME = 2.0  # seconds per inference
# Real vLLM sleep-mode wakes take ~0.1-0.8s (small models) to ~3-6s (large); 20s is the original placeholder.
WAKE_DELAYS = (0.5, 5.0, 20.0)
MAX_WORKERS = 40  # dynamic policies' provisioned pool; ~12.5 workers are busy on average
HISTORY_SEED_OFFSET = 1000  # history's past durations come from this other seed's trace, never the one replayed


def workload(seed: int, warn_share: float = 0.0, warning: float = 0.0) -> list[AgentTrace]:
    return generate(
        seed,
        num_agents=200,
        tool_calls_per_agent=20,
        median=30.0,
        spread=0.5,
        start_window=300.0,
        warn_share=warn_share,
        warning=warning,
    )


def forecast_idle_timeouts(wake_delay: float) -> tuple[float, ...]:
    """Idle timeouts for the forecasting policies (history, progress-aware), shared so both get the same choices.

    Longer than two wake delays just stays awake. 0 is the cheapest point, which a fair comparison needs: without
    it, progress-aware at a 5s wake looked 24% better than history on seed 0 from that gap alone.
    """
    return (0.0, wake_delay, 2 * wake_delay)


def run_all(seed: int, wake_delay: float) -> list[tuple[str, Result]]:
    """Every policy configuration on one seed's trace, which is generated once so all replay the same workload."""
    trace = workload(seed)
    starts = [a.start for a in trace]
    # What history would have logged from yesterday's runs: the same workload, a different seed.
    past = [d for agent in workload(seed + HISTORY_SEED_OFFSET) for d in agent.tool_durations]

    runs = []
    for n in range(8, 31, 2):
        runs.append((f"fixed N={n}", run_policy(trace, n, SERVICE_TIME, wake_delay)))
    # Short timeouts only pay off when wakes are fast; without them reactive is unfairly weak at 0.5s and 5s.
    for idle_timeout in (0.0, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0):

        def make_reactive(pool, idle_timeout=idle_timeout):
            return ReactivePolicy(pool, threshold=0, idle_timeout=idle_timeout)

        name = f"reactive idle={idle_timeout:.0f}s"
        runs.append((name, run_policy(trace, MAX_WORKERS, SERVICE_TIME, wake_delay, make_reactive)))
    for headroom in (0, 1, 2):
        for idle_timeout in forecast_idle_timeouts(wake_delay):

            def make_history(pool, headroom=headroom, idle_timeout=idle_timeout):
                return HistoryPolicy(pool, past, starts, headroom, idle_timeout)

            name = f"history h={headroom} idle={idle_timeout:g}s"
            runs.append((name, run_policy(trace, MAX_WORKERS, SERVICE_TIME, wake_delay, make_history)))
    runs.append(
        ("oracle", run_policy(trace, MAX_WORKERS, SERVICE_TIME, wake_delay, lambda pool: OraclePolicy(pool, starts)))
    )
    return runs


def cost(r: Result) -> float:
    """Active + waking: a policy that wakes often shouldn't look free."""
    return r.active_seconds + r.waking_seconds


def main() -> None:
    for wake_delay in WAKE_DELAYS:
        # Mean wait leaves out the fixed 2s of inference; p95 wait would just be p95 latency minus 2s.
        print(f"\nwake delay {wake_delay}s")
        print(
            f"{'policy':<26} {'p95 latency':>12} {'mean wait':>10} {'total worker-s':>15} {'active':>8} {'waking':>8}"
        )
        for name, r in sorted(run_all(SEED, wake_delay), key=lambda run: cost(run[1])):
            mean_wait = statistics.fmean(r.latencies) - SERVICE_TIME
            print(
                f"{name:<26} {r.p95:>11.2f}s {mean_wait:>9.3f}s {cost(r):>15.0f} {r.active_seconds:>8.0f}"
                f" {r.waking_seconds:>8.0f}"
            )


if __name__ == "__main__":
    main()
