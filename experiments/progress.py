"""Kill-criterion check for progress-aware across seeds: how much heads-up, from how many tools, gets p95 at least
15% lower than the best fair policy (reactive or history) at no more than 5% extra cost?

A share of tools announce their exact return a fixed time ahead (see `generate`). The traces' starts and durations
match `run.py`'s, so the baselines are the same runs. Only the fast wake delays: at 20s even the oracle mostly fails.
"""

from multiprocessing import Pool

from run import HISTORY_SEED_OFFSET, MAX_WORKERS, SERVICE_TIME, cost, forecast_idle_timeouts, run_all, workload
from seeds import COST_SLACK, LATENCY_BAR, SEEDS

from toolscale.experiment import run_policy
from toolscale.policies.progress import ProgressPolicy

WAKE_DELAYS = (0.5, 5.0)
WARN_SHARES = (0.25, 0.5, 1.0)  # prior art: progress was useful in about a quarter of runs
WARNINGS = (0.5, 1.0, 2.0, 5.0)  # seconds ahead; prior art: weak signals arrive about 1s ahead
HEADROOMS = (0, 1, 2)  # and idle timeouts as history's, so neither gets a choice the other lacks


def check(job: tuple[int, float]) -> tuple[int, float, dict, list[str]]:
    """One seed and wake delay: the best gain over the fair policies for every warning setting."""
    seed, wake_delay = job
    runs = dict(run_all(seed, wake_delay))
    fair = [r for name, r in runs.items() if name.startswith(("reactive", "history"))]
    starts = [a.start for a in workload(seed)]
    past = [d for agent in workload(seed + HISTORY_SEED_OFFSET) for d in agent.tool_durations]
    gains, problems = {}, []
    for share in WARN_SHARES:
        for warning in WARNINGS:
            trace = workload(seed, share, warning)
            best_gain = float("-inf")
            for headroom in HEADROOMS:
                for idle_timeout in forecast_idle_timeouts(wake_delay):

                    def make_progress(pool, headroom=headroom, idle_timeout=idle_timeout, share=share, warning=warning):
                        return ProgressPolicy(pool, past, starts, headroom, idle_timeout, share, warning)

                    r = run_policy(trace, MAX_WORKERS, SERVICE_TIME, wake_delay, make_progress)
                    budget = [f for f in fair if cost(f) <= (1 + COST_SLACK) * cost(r)]
                    # Nothing fair that cheap: compare with the cheapest, which already costs more.
                    best = min(budget, key=lambda f: f.p95) if budget else min(fair, key=cost)
                    best_gain = max(best_gain, 1 - r.p95 / best.p95)
                    # Sanity: warnings only add information, so progress should land between history and the
                    # oracle on both p95 and cost.
                    history = runs[f"history h={headroom} idle={idle_timeout:g}s"]
                    oracle = runs["oracle"]
                    if not (oracle.p95 <= r.p95 <= history.p95 and cost(oracle) <= cost(r) <= cost(history)):
                        problems.append(
                            f"wake {wake_delay:g}s seed {seed} p={share} W={warning} h={headroom} idle={idle_timeout:g}:"
                            f" progress {r.p95:.2f}s @ {cost(r):.0f}, history {history.p95:.2f}s @ {cost(history):.0f},"
                            f" oracle {oracle.p95:.2f}s @ {cost(oracle):.0f}"
                        )
            gains[share, warning] = best_gain
    return seed, wake_delay, gains, problems


def main() -> None:
    jobs = [(seed, wake_delay) for wake_delay in WAKE_DELAYS for seed in SEEDS]
    with Pool() as pool:  # each job is independent and single-threaded; spread them over the cores
        results = pool.map(check, jobs)
    for wake_delay in WAKE_DELAYS:
        print(f"\nwake delay {wake_delay}s")
        print(f"{'share':>6} {'warning':>8} {'seeds passing':>14} {'gain range':>16}")
        seeds = [gains for _, w, gains, _ in results if w == wake_delay]
        for share in WARN_SHARES:
            for warning in WARNINGS:
                g = [gains[share, warning] for gains in seeds]
                passed = sum(x >= LATENCY_BAR for x in g)
                print(f"{share:>6} {warning:>7g}s {passed:>9}/{len(g)} {min(g):>7.0%} to {max(g):>4.0%}")
    problems = [p for _, _, _, ps in results for p in ps]
    print(f"\n{len(problems)} runs outside history..oracle on p95 or cost; the first 20:")
    for p in problems[:20]:
        print(f"  {p}")


if __name__ == "__main__":
    main()
