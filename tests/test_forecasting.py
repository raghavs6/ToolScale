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


def test_silent_tool_is_not_due_within_the_lead_if_every_tool_warns():
    past = [10.0, 20.0, 30.0, 40.0]
    # A tool 15s in that hasn't warned can't end in (15, 25]: a warning 10s ahead would have come. Of the
    # durations it could still have (30, 40), one ends in (25, 35].
    assert expected_returns([15.0], past, 0.0, 10.0, warn_share=1.0, lead=10.0) == 0.0
    assert expected_returns([15.0], past, 10.0, 20.0, warn_share=1.0, lead=10.0) == pytest.approx(1 / 2)


def test_partial_warning_share_weights_durations_within_the_lead():
    past = [10.0, 20.0, 30.0, 40.0]
    # Half of tools warn: the 20s duration counts as 0.5, the 30s and 40s fully, so 0.5 / 2.5 for (15, 25].
    assert expected_returns([15.0], past, 0.0, 10.0, warn_share=0.5, lead=10.0) == pytest.approx(0.2)


def test_no_warnings_is_the_plain_forecast():
    past = [10.0, 20.0, 30.0, 40.0]
    assert expected_returns([0.0, 15.0], past, 0.0, 10.0, warn_share=0.0, lead=10.0) == expected_returns(
        [0.0, 15.0], past, 0.0, 10.0
    )
