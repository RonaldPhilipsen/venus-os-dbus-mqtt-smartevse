import math

from smartevse.payloads import battery_payload, grid_payload


def test_battery():
    assert battery_payload(2300, 230) == "100"
    assert battery_payload(-460, 230) == "-20"
    assert battery_payload(None, 230) is None  # Review Focus 4


def test_battery_non_finite_is_none():
    assert battery_payload(math.nan, 230) is None
    assert battery_payload(math.inf, 230) is None
    assert battery_payload(-math.inf, 230) is None


def test_battery_has_no_range_limit():
    assert battery_payload(230 * 300, 230) == "3000"


def test_grid_three_phase():
    assert grid_payload(2300, -460, 0, 1234.5, 230) == "100:-20:0:1840:1234500"


def test_grid_single_phase_and_missing_energy():
    assert grid_payload(230, None, None, None, 230) == "10:0:0:230:-1"


def test_grid_invalid():
    assert grid_payload(None, 0, 0, 1, 230) is None  # Review Focus 4
    assert grid_payload(46000, 0, 0, 1, 230) is None  # 2000 dA is out of range


def test_grid_phase_range_is_exclusive():
    # 1999 dA is the largest valid value, -1999 the smallest.
    assert grid_payload(1999 * 23, 0, 0, 0, 230) == "1999:0:0:45977:0"
    assert grid_payload(-1999 * 23, 0, 0, 0, 230) == "-1999:0:0:-45977:0"
    assert grid_payload(-2000 * 23, 0, 0, 0, 230) is None
    assert grid_payload(0, 2000 * 23, 0, 0, 230) is None


def test_grid_out_of_range_on_l2_or_l3_is_none():
    assert grid_payload(0, 46000, 0, 0, 230) is None
    assert grid_payload(0, 0, -46000, 0, 230) is None


def test_grid_none_phases_count_as_zero_in_sum():
    assert grid_payload(230, None, 460, 0, 230) == "10:0:20:690:0"


def test_grid_non_finite_phase_power_behaves_like_none():
    assert grid_payload(math.nan, 0, 0, 1, 230) is None
    assert grid_payload(230, math.nan, math.inf, 1, 230) == "10:0:0:230:1000"


def test_grid_non_finite_energy_is_missing():
    assert grid_payload(230, 0, 0, math.nan, 230) == "10:0:0:230:-1"
    assert grid_payload(230, 0, 0, math.inf, 230) == "10:0:0:230:-1"
