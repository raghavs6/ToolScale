"""Return-time forecasts: how many running tools are expected to come back within a time window."""

import bisect


def expected_returns(elapsed: list[float], past_durations: list[float], start: float, end: float) -> float:
    """Expected number of running tools that return in (now + start, now + end], from past durations alone.

    `elapsed` is how long each running tool has run so far; `past_durations` must be sorted. A tool that has run
    e seconds returns in the window with probability P(e + start < D <= e + end | D > e), counted over the past
    durations D. A window reaching into the past is cut at now: a tool still running didn't return then.
    A tool that has outlasted every past duration has no history to go on, so it is treated as due any moment.
    """
    start = max(start, 0.0)
    n = len(past_durations)

    def longer_than(x: float) -> int:
        return n - bisect.bisect_right(past_durations, x)

    total = 0.0
    for e in elapsed:
        survivors = longer_than(e)
        if survivors == 0:
            total += 1.0 if start == 0.0 else 0.0
        else:
            total += (longer_than(e + start) - longer_than(e + end)) / survivors
    return total
