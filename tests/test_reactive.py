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
