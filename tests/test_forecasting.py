import pytest

from toolscale.forecasting import expected_returns


def test_hand_example_from_design():
    # 100 past tools ran longer than 28s; 15 of them ended in (28, 30]. A tool 28s in has a 15% chance in the next 2s.
    past = sorted([10.0] * 50 + [29.0] * 15 + [40.0] * 85)
    assert expected_returns([28.0], past, 0.0, 2.0) == pytest.approx(0.15)


def test_sums_over_running_tools():
    past = [10.0, 20.0, 30.0, 40.0]
    # Tool at 0s: 1 of 4 ends in (0, 10]. Tool at 15s: 1 of 3 survivors (20, 30, 40) ends in (15, 25].
    assert expected_returns([0.0, 15.0], past, 0.0, 10.0) == pytest.approx(1 / 4 + 1 / 3)


def test_zero_when_no_past_duration_falls_in_the_window():
    assert expected_returns([5.0], [10.0, 20.0], 6.0, 14.0) == 0.0  # window covers 11-19s of runtime


def test_window_reaching_into_the_past_is_cut_at_now():
    past = [5.0, 10.0, 20.0]
    # (-5, 3] becomes (0, 3]: a tool at 8s can only return at 8-11s from here. Uncut, the window would also count
    # the 5s duration, which this tool has already outlasted.
    assert expected_returns([8.0], past, -5.0, 3.0) == expected_returns([8.0], past, 0.0, 3.0) == 0.5


def test_tool_longer_than_all_history_is_due_now():
    assert expected_returns([50.0], [10.0, 20.0], 0.0, 1.0) == 1.0
    assert expected_returns([50.0], [10.0, 20.0], 1.0, 2.0) == 0.0  # due now, so not later


def test_no_running_tools():
    assert expected_returns([], [10.0], 0.0, 5.0) == 0.0
