"""Kill-criterion check across seeds: is the oracle's p95 at least 15% lower than the best fair policy's
(reactive or history) at no more than 5% extra cost? The oracle bounds what any return forecast could gain."""

from run import WAKE_DELAYS, cost, run_all

SEEDS = range(10)
LATENCY_BAR = 0.15  # p95 at least this much lower...
COST_SLACK = 0.05  # ...than the best fair policy costing at most this much more than the oracle


def main() -> None:
    for wake_delay in WAKE_DELAYS:
        print(f"\nwake delay {wake_delay}s")
        passed = 0
        for seed in SEEDS:
            runs = run_all(seed, wake_delay)
            oracle = dict(runs)["oracle"]
            fair = [(name, r) for name, r in runs if name.startswith(("reactive", "history"))]
            budget = [(name, r) for name, r in fair if cost(r) <= (1 + COST_SLACK) * cost(oracle)]
            if budget:
                name, best = min(budget, key=lambda run: run[1].p95)
                note = ""
            else:
                # Nothing fair is that cheap; compare with the cheapest, which already costs more.
                name, best = min(fair, key=lambda run: cost(run[1]))
                note = f" (none within budget; cheapest costs {cost(best) / cost(oracle) - 1:+.0%})"
            gain = 1 - oracle.p95 / best.p95
            passed += gain >= LATENCY_BAR
            print(
                f"  seed {seed}: oracle {oracle.p95:.2f}s @ {cost(oracle):.0f} vs {name} {best.p95:.2f}s"
                f" @ {cost(best):.0f}{note}: {gain:.0%} lower"
            )
        print(f"  {passed}/{len(SEEDS)} seeds clear the bar")


if __name__ == "__main__":
    main()
