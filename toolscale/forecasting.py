"""Return-time forecasts: how many running tools are expected to come back within a time window."""

import bisect


def expected_returns(
    elapsed: list[float],
    past_durations: list[float],
    start: float,
    end: float,
    warn_share: float = 0.0,
    lead: float = 0.0,
) -> float:
    """Expected number of running tools that return in (now + start, now + end], from past durations alone.

    `elapsed` is how long each running tool has run so far; `past_durations` must be sorted. A tool that has run
    e seconds returns in the window with probability P(e + start < D <= e + end | D > e), counted over the past
    durations D. A window reaching into the past is cut at now: a tool still running didn't return then.
    A tool that has outlasted every past duration has no history to go on, so it is treated as due any moment.

    The running tools are ones that have not warned. If a share `warn_share` of tools warn `lead` seconds before
    returning, a silent tool returns within `lead` only if it is one that never warns, so durations in
    (e, e + lead] count with weight 1 - warn_share. Without this, a return in that span is counted twice: as a guess
    for the silent tool, and exactly once it warns. With warn_share 0 this is the plain history forecast.
    """
    start = max(start, 0.0)
    n = len(past_durations)

    def longer_than(x: float) -> int:
        return n - bisect.bisect_right(past_durations, x)

    def ended_in(lo: float, hi: float) -> int:  # past durations in (lo, hi]
        return longer_than(lo) - longer_than(hi) if lo < hi else 0

    quiet = 1.0 - warn_share  # weight of a duration within the lead: only tools that never warn are still silent
    total = 0.0
    for e in elapsed:
        cut = e + lead
        survivors = quiet * ended_in(e, cut) + longer_than(cut)
        if survivors == 0:
            total += 1.0 if start == 0.0 else 0.0
        else:
            lo, hi = e + start, e + end
            total += (quiet * ended_in(lo, min(hi, cut)) + ended_in(max(lo, cut), hi)) / survivors
    return total
