# ToolScale

Use live progress from AI agents' running tools to predict when those agents will need LLM inference again, and wake sleeping inference workers *before* the demand arrives.

> **Status:** early research project. No code yet. See [PROJECT.md](PROJECT.md) for the full brief.

## Why

AI agents alternate between LLM inference and tools (tests, builds, searches, downloads). Many tools can finish at once, sending a burst of agents back to inference. A controller that waits for the queue to grow wakes capacity too late. Tools that report progress may give earlier warning.

## Research question

When, and at what capacity cost, does live tool progress reduce inference latency compared with reactive and history-based policies?

## Approach

A discrete-event simulator in Python models agents cycling between inference and tools, with workers that are active, sleeping, or waking. Five policies run on identical workloads:

| Policy | Idea |
|---|---|
| Fixed | Constant number of active workers |
| Reactive | Wake on queue/utilization threshold |
| History-based | Forecast returns from past tool durations |
| **Progress-aware** | Forecast returns from live tool progress (proposed) |
| Oracle | Knows the future; upper bound only |

**Primary metrics:** p95 time from tool completion to next inference response, and total active-worker seconds.

## Success bar

Progress awareness should cut p95 post-tool latency by **≥15%** versus the best non-oracle baseline, at **≤5%** extra active-worker seconds, and hold up under noisy or missing progress. Otherwise, the idea is unsupported.

## Out of scope (v1)

No GPU provisioning, inference-engine changes, ML predictors, or production claims.
