# UPDATES

A daily log, newest first. Each entry says what was built and why.

## 2026-10-01

Added `WorkerPool` in `toolscale/workers.py`: identical always-on workers serve requests from a first-come-first-served queue, and each `Request` records its arrival, start, and finish times so wait and latency can be measured. Design decision: a finishing worker hands off directly to the next queued request, so a request arriving at the same instant can't cut ahead of one already waiting.

Added `Agent` in `toolscale/agents.py`: each agent alternates inference and tools from a fixed list of tool durations, and the pool notifies it via a `Request.on_done` callback. A test reproduces the core problem: two tools finishing together make the second agent's post-tool latency double (2s instead of 1s).

## 2026-09-30

Wrote the project brief (`PROJECT.md`), a README summarizing it, and `AGENTS.md` to set how we work (explain, agree, then build). Set up the Python project with `uv` and `pytest`, with a smoke test to prove the tooling runs. Built the discrete-event `Simulator` core in `toolscale/sim.py` with tests. Every later piece (agents, workers, policies) will schedule callbacks on it. Design decision: a sequence-number tie-breaker keeps events at the same time in the order they were scheduled, so an identical workload gives identical results across policies and comparisons stay fair. `run(until)` also leaves the clock at `until`, so elapsed time is the window we asked for, not the last event's time.
