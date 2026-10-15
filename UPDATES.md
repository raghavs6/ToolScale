# UPDATES

A daily log, newest first. Each entry says what was built and why.

## 2026-10-15

Added progress-aware (`ProgressPolicy`): history, plus an exact count for each tool that sends a heads-up. In the workload a share p of tools announce their return W seconds ahead (drawn on a separate random stream, so existing traces are unchanged). A first sweep failed everywhere, from two bugs (fixed, each with a test) and a design flaw: a silent tool still got history's guess, but if tools warn W ahead, a silent one can't be back within W unless it is a tool that never warns, so returns near the present were counted twice and more warnings made the policy costlier. Silent tools are now discounted within the lead by 1 - p, so the policy is told p and W (a real system would estimate them from its logs). History and progress now share the idle timeouts 0, w and 2w; without 0, progress looked 24% better at 5s from that gap alone. Across seeds 0-9 (`experiments/progress.py`), progress clears the kill criterion only when every tool warns at least one wake delay ahead: at 0.5s, p=1 passes 10/10 at any W (20%, matching the oracle); at 5s, only p=1 with W=5s passes (10/10, 24-35%). At p=0.5 it gains 0-12%, and at the prior-art p=0.25 at most 8% (at 0.5s, at most 3%). So progress has to be nearly universal and early to be worth it here: history already gets most of what partial warning offers. The run's sanity check flagged 1,785 runs, but the ones shown are progress paying about 1% more cost than history at the same knobs for a lower p95; a check on p95 alone would be the right one. The oracle verdicts in `seeds.py` predate history's idle=0 baseline, which can only narrow the oracle's margins.

**Next:** decide whether to pursue richer progress signals (bars, noisy estimates) or test bursty workloads, where history's average is weakest.

## 2026-10-14 (later)

Added the history-based baseline (`HistoryPolicy`): it forecasts returns from how long each running tool has run and past tool durations from another seed's trace, never from progress or the tool's real duration, and uses the oracle's rule plus a headroom knob and an idle timeout. The timeout was needed: history's forecast is an average, so without it history kept sleeping workers and re-waking them, and at a 20s wake delay lost to reactive at every headroom. With it, history beats reactive at 0.5s (p95 2.28s vs 2.50s at similar cost on seed 0), ties at 5s, and nearly matches the oracle at 20s. `experiments/seeds.py` now checks the kill criterion against the best of reactive or history across seeds 0-9: the oracle clears it at 0.5s (10/10, 20% lower p95) and 5s (10/10, 25-53%) but no longer at 20s (3/10; on 5 seeds history comes within 0-2% of the oracle). So with slow wakes, knowing exact return times adds almost nothing over history; any case for progress rests on fast wakes, where only about one wake delay of warning is needed.

**Next:** progress-aware with realistic warning, at 0.5s and 5s wake delays.

## 2026-10-14

Added an oracle policy (`OraclePolicy`): it is told each tool's return time when the tool starts and wakes workers to land just in time, so it bounds what any return forecast, progress-aware included, could gain. `experiments/run.py` now runs fixed, reactive, and oracle at wake delays of 0.5s, 5s (the range of real vLLM sleep-mode wakes) and 20s, judges cost as active + waking worker-s, and adds reactive idle timeouts down to 0s, without which reactive was unfairly weak at short wake delays. On one seed, the oracle clears the kill criterion's bar (p95 at least 15% lower at no more than 5% extra cost) at 0.5s (p95 2.00s at 9,572 worker-s vs reactive idle=0s's 2.50s at 9,795) and at 5s (2.00s at 12,951; no reactive point is that cheap, and the cheapest, idle=2s, is 3.84s at 13,805), but not at 20s, where reactive idle=30s also reaches 2.00s for only 4% more (16,595 vs 15,963). Across seeds 0-9 the verdicts hold at 0.5s (10/10 pass, 20% lower p95 every time) and 5s (10/10, 26-56% lower, usually with no reactive point within 5% of the oracle's cost); at 20s it is marginal (8/10 pass, mostly at 16-24%, and seeds 0 and 8 fail). So the ceiling is real, and it is largest when wakes are fast, which is also when a forecast needs the least warning: about one wake delay.

**Next:** decide between the history-based baseline and progress-aware with realistic warning.

## 2026-10-12

Dropped the drain-aware variant from `ReactivePolicy`; simple reactive is now the only reactive baseline. Its check ignored ongoing arrivals, and fixing that needs a forecast of arrivals, because a queue snapshot looks the same whether a burst is ending or steady load continues. That makes it a forecasting policy, so the arrival-rate fix moves to the history-based baseline, where it can share progress-aware's decision rule and differ only in its forecast.

Policy runs now start with every worker asleep (fixed still starts with its N awake). The workload starts empty, so the old all-awake start billed reactive for capacity it never chose: up to 8,379 of idle=300s's 30,634 worker-s, at unchanged p95. A warm-up exclusion was rejected because the workload has no steady state; its ramp-up is real demand. With the cold start, reactive with idle timeouts up to 120s beats fixed at matched latency (e.g. idle=10s: p95 2.52s at 12,989 worker-s vs fixed N=14's 2.55s at 16,860); idle=300s still loses to fixed N=18 (both 2.00s; 22,255 vs 21,664).

## 2026-10-05

Ran the first comparison (`experiments/run.py`, one seed, placeholder settings): simple reactive beat fixed on both latency and cost at matched points (e.g. p95 2.00s at 16,731 worker-s vs fixed N=14's 2.55s at 16,860), but drain-aware did worse than fixed: under steady load it lets requests wait up to `wake_delay`, because its "line clears before a wake lands" check ignores requests that keep arriving. Cost is billed only until the last request finishes (`Agent.on_finished`), since billing to the end of the run added up to 4.1% to reactive. Reactive wins because the load ramps up, peaks, and trails off (sampled busy workers: 3 at t=100s, 17 at 300s, 0 at 1100s); fixed N=14 overpays at the ends and queues at the peaks. Long idle timeouts are inflated by the startup state (all 40 workers awake at t=0: up to 12,000 of reactive idle=300s's 30,634 worker-s).

**Next:** fix or drop the drain-aware rule (likely: account for the arrival rate), then decide how to handle the startup transient. Both are in PROJECT.md's open questions.

Chose event-driven policies over a periodic tick: a tick adds made-up observation delay that hurts the reactive baseline more than forecasting policies. `WorkerPool` now notifies an `on_change` listener (as a zero-delay event, so a burst is seen whole) on arrivals, finishes, and completed wakes, but not on `wake()`/`sleep()`, which would let a policy re-trigger itself forever. Added `ReactivePolicy` with a queue threshold and an optional drain-aware check; an experiment showed neither variant dominates (drain-aware skips wasted wakes but is slower when a second burst follows), so both are kept as baselines.

The reactive policy now also sleeps workers idle for `idle_timeout`. To make that work, the pool records when each idle worker went idle and hands new work to the most recently idle one (LIFO); with FIFO, a steady trickle rotates through every worker and none ever times out. The policy keeps at most one timer, for the oldest idle worker's deadline. Added `workloads.generate`: seeded traces (agent start times, lognormal tool durations) drawn up front, because drawing randomness mid-simulation was shown to hand different policies different tool durations from the same seed.

## 2026-10-02

`WorkerPool` now meters capacity cost: `worker_seconds()` returns active and waking worker-seconds, updated whenever the worker counts change. Design decision: idle active workers cost the same as busy ones, and waking time is tracked separately so experiments can report the cost of wasted wakes on their own.

## 2026-10-01

Added `WorkerPool` in `toolscale/workers.py`: identical always-on workers serve requests from a first-come-first-served queue, and each `Request` records its arrival, start, and finish times so wait and latency can be measured. Design decision: a finishing worker hands off directly to the next queued request, so a request arriving at the same instant can't cut ahead of one already waiting.

Added `Agent` in `toolscale/agents.py`: each agent alternates inference and tools from a fixed list of tool durations, and the pool notifies it via a `Request.on_done` callback. A test reproduces the core problem: two tools finishing together make the second agent's post-tool latency double (2s instead of 1s).

Workers can now be active, waking, or sleeping (`wake(n)` takes `wake_delay`, `sleep(n)` is instant and skips busy workers), and the pool asserts its invariants after every state change. Design decision: wakes can't be cancelled, so a wrong wake costs its full delay, which keeps the comparison conservative against the progress-aware policy.

## 2026-09-30

Wrote the project brief (`PROJECT.md`), a README summarizing it, and `AGENTS.md` to set how we work (explain, agree, then build). Set up the Python project with `uv` and `pytest`, with a smoke test to prove the tooling runs. Built the discrete-event `Simulator` core in `toolscale/sim.py` with tests. Every later piece (agents, workers, policies) will schedule callbacks on it. Design decision: a sequence-number tie-breaker keeps events at the same time in the order they were scheduled, so an identical workload gives identical results across policies and comparisons stay fair. `run(until)` also leaves the clock at `until`, so elapsed time is the window we asked for, not the last event's time.
