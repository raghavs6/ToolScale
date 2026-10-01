import pytest

from toolscale.sim import Simulator


def test_events_run_in_time_order():
    sim = Simulator()
    ran = []
    sim.schedule(5.0, lambda: ran.append("a"), name="a")
    sim.schedule(2.0, lambda: ran.append("b"), name="b")
    sim.schedule(3.0, lambda: ran.append("c"), name="c")
    sim.run()
    assert ran == ["b", "c", "a"]
    assert sim.now == 5.0


def test_same_time_events_run_in_schedule_order():
    sim = Simulator()
    ran = []
    for label in ["first", "second", "third"]:
        sim.schedule(1.0, lambda label=label: ran.append(label), name=label)
    sim.run()
    assert ran == ["first", "second", "third"]


def test_event_scheduled_during_run_is_processed():
    sim = Simulator()
    seen = []

    def tool_done():
        seen.append(("tool_done", sim.now))
        sim.schedule(1.0, lambda: seen.append(("inference_done", sim.now)), name="inference_done")

    sim.schedule(2.0, tool_done, name="tool_done")
    sim.run()
    assert seen == [("tool_done", 2.0), ("inference_done", 3.0)]


def test_run_until_stops_on_time_and_keeps_later_events():
    sim = Simulator()
    ran = []
    sim.schedule(7.0, lambda: ran.append(7), name="e7")
    sim.schedule(10.0, lambda: ran.append(10), name="e10")
    sim.schedule(12.0, lambda: ran.append(12), name="e12")

    sim.run(until=10.0)
    assert ran == [7, 10]  # event exactly at `until` runs (decision A)
    assert sim.now == 10.0  # clock lands on `until` (decision B)

    sim.run(until=20.0)
    assert ran == [7, 10, 12]
    assert sim.now == 20.0


def test_negative_delay_raises():
    sim = Simulator()
    with pytest.raises(ValueError):
        sim.schedule(-1.0, lambda: None, name="bad")


def test_log_records_time_and_name():
    sim = Simulator()
    sim.schedule(2.0, lambda: None, name="tool_done")
    sim.schedule(1.0, lambda: None, name="wake_done")
    sim.run()
    assert sim.log == [(1.0, "wake_done"), (2.0, "tool_done")]
