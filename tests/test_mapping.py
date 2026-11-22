import pytest

from smartevse.mapping import (power_reading, victron_mode,
                               victron_set_current, victron_start_stop,
                               victron_status)
from smartevse.state import EvseState


@pytest.mark.parametrize("evse,last,expected", [
    ("Smart", 1, 0), ("Normal", 1, 0), ("Solar", 0, 1),
    ("Pause", 1, 1), ("Off", 0, 0), ("N/A", 1, 1), (None, 1, 1),
])
def test_victron_mode(evse, last, expected):
    assert victron_mode(evse, last) == expected


@pytest.mark.parametrize("evse,last,expected", [
    ("Smart", 0, 1), ("Solar", 0, 1), ("Pause", 1, 0), ("Off", 1, 0),
    ("N/A", 1, 1), (None, 0, 0), ("Normal", 0, 1),
])
def test_start_stop(evse, last, expected):
    assert victron_start_stop(evse, last) == expected


def st(**kw):
    s = EvseState()
    s.error = "None"
    s.plug = "Connected"
    s.mode = "Smart"
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def test_status():
    assert victron_status(st(error="RCM Tripped")) == 8
    assert victron_status(st(error="Temperature High")) == 8
    assert victron_status(st(state="Ready to Charge", plug="Disconnected")) == 0
    assert victron_status(st(state="Charging")) == 2
    assert victron_status(st(state="Connected to EV", mode="Solar")) == 4
    assert victron_status(st(state="Connected to EV", mode="Pause")) == 6
    assert victron_status(st(state="Connected to EV", mode="Off")) == 6
    assert victron_status(st(state="Connected to EV")) == 1


def test_status_error_not_received_is_no_error():
    assert victron_status(st(error=None, state="Charging")) == 2


def test_set_current_prefers_override():
    assert victron_set_current(st(override_da=83, charge_current_da=160)) == 8.3
    assert victron_set_current(st(override_da=0, charge_current_da=160)) == 16.0
    assert victron_set_current(st()) is None
    assert victron_set_current(st(override_da=0)) is None


def test_power_with_ev_meter_scales_phases_to_total():
    s = st(state="Charging", ev_power_w=6900, ev_current_da=[100, 100, 100])
    r = power_reading(s, has_ev_meter=True, nominal_voltage=230)
    assert r.total_w == 6900 and r.l1_w == pytest.approx(2300)
    assert r.current_a == 10.0


def test_power_with_ev_meter_uneven_phases():
    s = st(ev_power_w=3000, ev_current_da=[100, 50, 0])
    r = power_reading(s, True, 230)
    assert (r.l1_w, r.l2_w, r.l3_w) == pytest.approx((2000, 1000, 0))
    assert r.l1_w + r.l2_w + r.l3_w == pytest.approx(3000)


def test_power_with_ev_meter_missing_values():
    r = power_reading(st(), True, 230)
    assert r == (0, 0, 0, 0, 0)
    s = st(ev_power_w=1000, ev_current_da=[None, None, None])
    r = power_reading(s, True, 230)
    assert r.total_w == 1000 and r.l1_w == 1000 and r.l2_w == 0
    assert r.current_a == 0


def test_power_estimate_without_ev_meter():
    s = st(state="Charging", charge_current_da=160, phases=3)
    r = power_reading(s, False, 230)
    assert r.total_w == pytest.approx(11040)
    assert r.l1_w == pytest.approx(3680) and r.l3_w == pytest.approx(3680)
    assert r.current_a == 16.0
    s.state = "Connected to EV"
    assert power_reading(s, False, 230).total_w == 0


def test_power_estimate_single_phase_and_unknown_phases():
    s = st(state="Charging", charge_current_da=100, phases=1)
    r = power_reading(s, False, 230)
    assert r.l1_w == pytest.approx(2300) and r.l2_w == 0 and r.l3_w == 0
    s.phases = None
    assert power_reading(s, False, 230).total_w == pytest.approx(2300)
