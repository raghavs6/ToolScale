from toolscale.policies.reactive import ReactivePolicy
from toolscale.sim import Simulator
from toolscale.workers import Request, WorkerPool


def burst(threshold, num_workers=4):
    """1 active worker, the rest asleep; service 10s, wake 2s; 3 requests arrive together at t=0."""
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=num_workers, service_time=10.0, wake_delay=2.0, initial_active=1)
    ReactivePolicy(pool, threshold=threshold)
    reqs = [Request(id=str(i)) for i in range(3)]
    for r in reqs:
        pool.submit(r)
    sim.run()
    return pool, reqs


def test_wakes_one_worker_per_waiting_request():
    pool, reqs = burst(threshold=0)
    # 2 wait, so 2 wake; the 3 notices in the burst don't triple that, because waking workers count.
    assert pool.sleeping == 1
    assert [r.finish for r in reqs] == [10.0, 12.0, 12.0]  # with no policy: [10, 20, 30]


def test_threshold_tolerates_some_waiting():
    pool, reqs = burst(threshold=1)
    assert pool.sleeping == 2  # only the request beyond the threshold gets a worker
    assert [r.finish for r in reqs] == [10.0, 12.0, 20.0]


def test_wakes_no_more_than_are_sleeping():
    pool, reqs = burst(threshold=0, num_workers=2)
    assert pool.sleeping == 0
    assert [r.finish for r in reqs] == [10.0, 12.0, 20.0]


def bursts(drain_aware, arrivals):
    """1 active + 4 asleep; service 1s, wake 5s, so active workers often clear a line before a wake lands."""
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=5, service_time=1.0, wake_delay=5.0, initial_active=1)
    ReactivePolicy(pool, threshold=0, drain_aware=drain_aware)
    reqs = []
    for t, n in arrivals:
        for _ in range(n):
            r = Request(id=str(len(reqs)))
            reqs.append(r)
            sim.schedule(t, lambda r=r: pool.submit(r), name="arrive")
    sim.run()
    return pool, max(r.finish - r.arrival for r in reqs)


def test_drain_aware_skips_wakes_that_would_land_too_late():
    # Lone burst of 3: the active worker clears it by t=3, before any woken worker (t=5) could help.
    simple_pool, simple_max = bursts(drain_aware=False, arrivals=[(0, 3)])
    drain_pool, drain_max = bursts(drain_aware=True, arrivals=[(0, 3)])
    assert simple_pool.sleeping == 2  # simple wastes 2 wakes
    assert drain_pool.sleeping == 4  # drain-aware wakes nothing
    assert drain_max == simple_max == 3.0  # at no latency cost


def test_drain_aware_is_slower_when_a_burst_follows():
    # Simple's "wasted" wakes at t=0 land at t=5, just in time for the second burst at t=4.
    _, simple_max = bursts(drain_aware=False, arrivals=[(0, 3), (4, 8)])
    _, drain_max = bursts(drain_aware=True, arrivals=[(0, 3), (4, 8)])
    assert (simple_max, drain_max) == (4.0, 6.0)


def test_drain_aware_wakes_when_no_worker_is_active():
    # With 0 active workers the line never drains on its own, so a wake is always needed.
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=1, service_time=1.0, wake_delay=5.0, initial_active=0)
    ReactivePolicy(pool, threshold=0, drain_aware=True)
    req = Request(id="0")
    pool.submit(req)
    sim.run()
    assert req.finish == 6.0
