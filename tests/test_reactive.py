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


def timer_times(sim):
    return [t for t, name in sim.log if name == "policy_timer"]


def test_idle_workers_sleep_after_timeout():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=2, service_time=1.0)
    ReactivePolicy(pool, threshold=0, idle_timeout=5.0)
    pool.submit(Request(id="0"))
    sim.run()
    # Untouched worker idle since 0 sleeps at 5; the one that served is idle since 1 and sleeps at 6.
    assert pool.sleeping == 2
    assert pool.worker_seconds()[0] == 5.0 + 6.0


def test_initially_idle_workers_sleep_without_any_request():
    # No pool notice ever fires, so only the decide() at construction can set the first timer.
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=2, service_time=1.0)
    ReactivePolicy(pool, threshold=0, idle_timeout=5.0)
    sim.run()
    assert pool.sleeping == 2
    assert pool.worker_seconds()[0] == 10.0


def test_spare_worker_sleeps_under_steady_load_with_few_timers():
    # 1 request every 2s, 1s each: one worker carries it all (LIFO), the spare sleeps at t=5.
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=2, service_time=1.0)
    ReactivePolicy(pool, threshold=0, idle_timeout=5.0)
    for t in range(0, 100, 2):
        sim.schedule(t, lambda t=t: pool.submit(Request(id=str(t))), name="arrive")
    sim.run()
    assert pool.worker_seconds()[0] == 5.0 + 104.0  # spare until 5; worker idle since 99 sleeps at 104
    notices = sum(1 for _, name in sim.log if name == "pool_change")
    assert len(timer_times(sim)) < notices / 4  # about one per timeout window, not one per notice


def test_timer_that_fires_a_hair_early_refires_on_the_deadline():
    # Delay = deadline - now, and now + (deadline - now) rounds one step short for these exact values.
    now, deadline = 260.4923103919594, 805.0278270130224
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=1, service_time=1.0)  # idle since t=0
    sim.run(until=now)
    ReactivePolicy(pool, threshold=0, idle_timeout=deadline)  # sets its first timer at `now`
    sim.run()
    assert timer_times(sim) == [805.0278270130223, deadline]  # early, then exact
    assert pool.sleeping == 1
    assert pool.worker_seconds()[0] == deadline
