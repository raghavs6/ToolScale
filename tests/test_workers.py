import pytest

from toolscale.sim import Simulator
from toolscale.workers import Request, WorkerPool


def test_hand_example_two_workers_three_requests():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=2, service_time=1.0)
    reqs = [Request(id=str(i)) for i in range(3)]
    for r in reqs:
        pool.submit(r)
    sim.run()
    assert [(r.start, r.finish) for r in reqs] == [(0.0, 1.0), (0.0, 1.0), (1.0, 2.0)]
    assert reqs[2].start - reqs[2].arrival == 1.0  # third request waited 1s


def test_idle_worker_serves_immediately():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=1, service_time=1.0)
    sim.schedule(3.0, lambda: pool.submit(req), name="arrive")
    req = Request(id="0")
    sim.run()
    assert req.arrival == req.start == 3.0
    assert req.finish == 4.0


def test_queue_is_first_come_first_served():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=1, service_time=1.0)
    reqs = [Request(id=str(i)) for i in range(3)]
    for r in reqs:
        pool.submit(r)
    sim.run()
    assert [r.finish for r in reqs] == [1.0, 2.0, 3.0]


def test_worker_freed_for_later_arrival():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=1, service_time=1.0)
    a, b = Request(id="0"), Request(id="1")
    pool.submit(a)
    sim.schedule(5.0, lambda: pool.submit(b), name="arrive_b")
    sim.run()
    assert a.finish == 1.0
    assert b.start == 5.0  # no wait: worker was free again
    assert pool.busy == 0


def test_on_done_called_at_finish_after_handoff():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=1, service_time=1.0)
    seen = []
    a = Request(id="0", on_done=lambda r: seen.append((r.id, sim.now, len(pool.queue))))
    b = Request(id="1")
    pool.submit(a)
    pool.submit(b)
    sim.run()
    # At a's finish, b has already been handed the worker, so the queue is empty.
    assert seen == [("0", 1.0, 0)]


def test_check_catches_corrupted_state():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=1, service_time=1.0)
    pool.busy = 1  # pretend the worker is busy, but nothing is running
    pool.idle_since.pop()  # keep the pretense consistent: a busy worker isn't idle
    pool.submit(Request(id="0"))  # queues fine: busy == num_workers
    pool.busy = 0  # now a request waits while a worker is idle
    with pytest.raises(AssertionError, match="waiting while a worker is idle"):
        pool._check()


def test_request_waits_for_wake():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=1, service_time=1.0, wake_delay=5.0, initial_active=0)
    req = Request(id="0")
    pool.submit(req)
    pool.wake(1)
    assert (pool.active, pool.waking, pool.sleeping) == (0, 1, 0)
    sim.run()
    assert (req.start, req.finish) == (5.0, 6.0)
    assert (pool.active, pool.waking, pool.sleeping) == (1, 0, 0)


def test_sleeping_worker_never_serves():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=1, service_time=1.0, initial_active=0)
    req = Request(id="0")
    pool.submit(req)
    sim.run()
    assert req.start is None
    assert list(pool.queue) == [req]


def test_woken_worker_drains_queue_alongside_active_one():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=2, service_time=1.0, wake_delay=0.5, initial_active=1)
    reqs = [Request(id=str(i)) for i in range(3)]
    for r in reqs:
        pool.submit(r)
    pool.wake(1)
    sim.run()
    assert [(r.start, r.finish) for r in reqs] == [(0.0, 1.0), (0.5, 1.5), (1.0, 2.0)]


def test_sleep_skips_busy_workers():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=2, service_time=1.0)
    pool.submit(Request(id="0"))
    pool.sleep(2)
    assert (pool.active, pool.busy, pool.sleeping) == (1, 1, 1)


def test_wake_and_sleep_clamp_to_available_workers():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=2, service_time=1.0, wake_delay=1.0, initial_active=1)
    pool.wake(5)  # only 1 sleeping
    assert (pool.active, pool.waking, pool.sleeping) == (1, 1, 0)
    pool.sleep(5)  # only the idle active one sleeps; the waking one is untouched
    assert (pool.active, pool.waking, pool.sleeping) == (0, 1, 1)
    sim.run()
    assert (pool.active, pool.waking, pool.sleeping) == (1, 0, 1)


def test_invalid_initial_active_rejected():
    with pytest.raises(AssertionError):
        WorkerPool(Simulator(), num_workers=1, service_time=1.0, initial_active=2)


def test_worker_seconds_counts_waking_separately():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=2, service_time=1.0, wake_delay=2.0, initial_active=1)
    pool.wake(1)
    sim.run(until=10.0)
    assert pool.worker_seconds() == (18.0, 2.0)  # active: 1x10 + 1x8; waking: 1x2


def test_worker_seconds_stop_when_asleep():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=2, service_time=1.0)
    sim.schedule(4.0, lambda: pool.sleep(1), name="sleep")
    sim.run(until=10.0)
    assert pool.worker_seconds() == (14.0, 0.0)  # 2x4 + 1x6


def test_busy_and_idle_workers_cost_the_same():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=1, service_time=3.0)
    pool.submit(Request(id="0"))
    sim.run(until=10.0)
    assert pool.worker_seconds() == (10.0, 0.0)  # 3s busy + 7s idle


def test_on_change_sees_whole_burst():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=1, service_time=1.0)
    seen = []
    pool.on_change = lambda: seen.append((sim.now, pool.busy, len(pool.queue)))
    for i in range(3):
        sim.schedule(5.0, lambda i=i: pool.submit(Request(id=str(i))), name=f"arrive{i}")
    sim.run(until=5.0)
    # All three arrivals run before the first notice, so it sees the full burst.
    assert seen[0] == (5.0, 1, 2)


def test_on_change_is_scheduled_not_called_inline():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=1, service_time=1.0)
    seen = []
    pool.on_change = lambda: seen.append(sim.now)
    pool.submit(Request(id="0"))
    assert seen == []  # submit has returned, but the notice hasn't run yet
    sim.run(until=0.0)
    assert seen == [0.0]


def test_on_change_fires_on_finish():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=1, service_time=1.0)
    seen = []
    pool.on_change = lambda: seen.append(sim.now)
    pool.submit(Request(id="0"))
    sim.run()
    assert seen == [0.0, 1.0]  # arrival, then finish


def test_on_change_fires_on_wake_done_but_not_wake_or_sleep():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=2, service_time=1.0, wake_delay=3.0, initial_active=1)
    seen = []
    pool.on_change = lambda: seen.append(sim.now)
    pool.wake(1)
    pool.sleep(1)
    sim.run()
    # wake() and sleep() are the policy's own actions; only the wake completing is news.
    assert seen == [3.0]


def test_idle_since_records_when_each_idle_worker_went_idle():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=2, service_time=1.0)
    pool.submit(Request(id="0"))
    sim.run()
    # The untouched worker has been idle since t=0; the one that served has been idle since it finished.
    assert list(pool.idle_since) == [0.0, 1.0]


def test_reuses_most_recently_idle_worker():
    # Steady load: 1 request every 2s, each takes 1s. LIFO gives every request to the same worker,
    # so the other stays idle since t=0 and can later time out. (FIFO would alternate them.)
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=2, service_time=1.0)
    for t in range(0, 100, 2):
        sim.schedule(t, lambda t=t: pool.submit(Request(id=str(t))), name="arrive")
    sim.run()
    assert list(pool.idle_since) == [0.0, 99.0]


def test_sleep_takes_longest_idle_worker():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=2, service_time=1.0)
    pool.submit(Request(id="0"))
    sim.run(until=2.0)
    pool.sleep(1)
    assert list(pool.idle_since) == [1.0]  # the worker idle since t=0 went to sleep


def test_woken_worker_with_no_queue_is_idle_from_wake_done():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=1, service_time=1.0, wake_delay=3.0, initial_active=0)
    pool.wake(1)
    sim.run()
    assert list(pool.idle_since) == [3.0]


def test_check_catches_idle_since_out_of_sync():
    sim = Simulator()
    pool = WorkerPool(sim, num_workers=2, service_time=1.0)
    pool.idle_since.pop()  # 2 idle workers, but only 1 recorded
    with pytest.raises(AssertionError, match="idle_since"):
        pool._check()
