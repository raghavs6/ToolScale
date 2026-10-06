# UPDATES

A daily log, newest first. Each entry says what was built and why.

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
