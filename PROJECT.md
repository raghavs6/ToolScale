# ToolScale

**One sentence:** Use live progress from AI agents' running tools to predict when those agents will need LLM inference again, then wake existing sleeping inference workers before the demand arrives.

## Problem and motivation

AI agents alternate between LLM inference and external tools such as tests, builds, searches, and downloads. While a tool runs, its agent does not need an inference worker. Many tools can finish close together, returning agents to inference at once. A controller that waits for the inference queue to grow may wake capacity too late, increasing response latency. Some tools expose progress that could provide earlier warning.

## Research question

**When, and at what capacity cost, does live tool progress let a controller reduce inference latency compared with reactive and history-based capacity policies?**

## Core idea

Collect progress updates from running tools, estimate how many agents will return within a short horizon, and wake enough *already provisioned* sleeping workers to serve the forecast demand. Account for wake time, current queue, active capacity, and uncertainty. Keep a worker awake only while expected near-term demand justifies it.

## Goals and non-goals

**Goals**
- Build a small, reproducible simulator and compare policies on identical workloads.
- Measure latency, active worker time, wake activity, and forecast quality across varied tool behaviors.
- Find the conditions under which progress signals help, hurt, or add no value.
- Produce a clear policy and experiment results that can later be checked with real traces.

**Non-goals for the first version**
- Starting new GPU machines or scaling a Kubernetes cluster.
- Modifying an inference engine, running GPUs, or claiming production readiness.
- Training an ML predictor or optimizing low-level serving code.

## Simple tech stack

Python 3.11+ for the simulator, policies, and experiment runner; standard-library data structures and JSON/YAML configuration. Use NumPy/pandas for analysis and matplotlib for plots when useful. Docker is optional for reproducibility. Consider vLLM integration only after simulation shows a worthwhile effect. 

## Architecture and simulator model

```text
tool events/progress ──> return-time estimator ──> capacity policy ──> worker sleep/wake
        │                                               │
        └──────────────> discrete-event simulator <──────┘
                                      │
                         latency and capacity metrics
```

The discrete-event simulator models agents cycling through inference requests and tools. Each inference worker has a configurable service rate, queue, state (active, sleeping, waking), and wake delay. Tool instances have a start time, duration, and optional timestamped progress observations. Requests queue when active capacity is insufficient. Begin with simple fixed or sampled inference service times and tool durations; add bursty arrivals, multiple tool types, and imperfect progress observations. Use the same workload traces and random seeds for every policy. This is a capacity model, not a detailed GPU performance model.

## Policies to compare

1. **Fixed capacity:** Keep a fixed number of workers active; provides a simple latency/cost reference.
2. **Reactive:** Wake workers when queue length or utilization exceeds a threshold; sleep after an idle timeout. Two variants: *simple* (one worker per request waiting beyond the threshold) and *drain-aware* (skip waking when active workers will clear the line before a wake lands). Neither dominates: drain-aware avoids wasted wakes but reacts later when a second burst follows, so evaluation compares against both.
3. **History-based:** Forecast returns from past tool durations and starts, without live progress.
4. **Progress-aware (proposed):** Forecast near-term returns from each running tool's latest progress, elapsed time, and tool type. Combine expected returns with queued demand and active service capacity. Wake workers if the estimated shortfall during the wake horizon exceeds a threshold; use a cooldown/idle timeout to avoid oscillation.
5. **Oracle:** Know future tool completion times; use only as an upper-bound reference, never as an attainable baseline.

Start the progress-aware estimator with a transparent rule, such as remaining time = elapsed time × (1 − progress) / max(progress, ε), capped by reasonable per-tool bounds. Compare it with a duration-history estimate and fall back to history when progress is absent or unreliable. Tune thresholds on separate scenarios, then freeze them for evaluation.

## Metrics and experiment plan

**Primary:** p95 time from tool completion to the next inference response, and total active-worker seconds (capacity cost). **Secondary:** p50/p99 response latency, queue length/spike duration, wakes per hour, time spent waking, forecast error and calibration, and missed or unnecessary wakes.

Run paired simulations across steady and bursty workloads. Vary tool-duration spread, completion synchronization, progress-update frequency, progress noise/bias, missing signals, wake delay, worker service rate, and utilization. Include workloads where progress is uninformative. Compare policies at similar capacity cost and also plot latency versus active-worker seconds. Report multiple seeds with uncertainty intervals; keep tuning and evaluation scenarios separate. If possible, replay anonymized real tool traces after the synthetic study.

## Milestones

1. **Model:** Implement the event simulator, trace generator, and fixed/reactive policies; validate simple hand-checkable cases.
2. **Signals:** Add progress observations, history-based forecast, and forecast-quality plots.
3. **Policy:** Add progress-aware wake/sleep decisions and oracle reference.
4. **Evaluation:** Run the paired experiment matrix, sensitivity checks, and cost/latency plots.
5. **Reality check:** Test with real traces or a small serving prototype only if the simulation result is promising.

## Repo layout

```text
toolscale/
├── README.md
├── project.md
├── configs/                 # workload and worker parameters
├── toolscale/
│   ├── sim.py               # event engine: clock + time-ordered callbacks
│   ├── workers.py           # inference workers and request queue
│   ├── agents.py            # agents alternating inference and tool calls
│   ├── workloads.py         # synthetic traces and optional replay
│   ├── forecasting.py       # return-time estimates
│   └── policies/            # fixed, reactive, history, progress, oracle
├── experiments/
│   └── run.py               # paired policy comparisons
└── analysis/
    └── plots.py             # metrics and figures
```

## Kill criteria

Treat the idea as unsupported if, on held-out realistic scenarios, progress awareness cannot lower p95 post-tool latency by **at least 15%** versus the strongest non-oracle baseline at **no more than 5%** extra active-worker seconds, or if gains disappear with plausible missing/noisy progress. Also stop pursuing live integration if observed wake delays are longer than the available warning for most returns. These are provisional decision thresholds, not claimed results; revise them before evaluation if actual system costs call for it.

## Open questions

- **Progress-aware decision cost at scale.** Policies run `decide()` on every pool notice (~210k calls at 5,000 agents × 20 tool calls). If the progress-aware `decide()` scans every running tool, that is ~10⁹ operations per run. Measure it at real experiment sizes once the policy exists; if slow, run `decide()` once per instant or update the forecast incrementally. Neither fix affects the pool or the reactive policy.

## Next steps

Define the first workload and worker parameters; implement the minimal event simulator and two baseline policies; verify a small burst example by hand; then add progress signals and run the first paired comparison. Record assumptions and results in the repository so the project can be reproduced.
