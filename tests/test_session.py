import pytest

from smartevse.mapping import PowerReading
from smartevse.session import Session
from smartevse.state import EvseState


def test_charging_time_and_estimated_energy():
    sess, s = Session(), EvseState(state="Charging", plug="Connected")
    r = PowerReading(3600, 3600, 0, 0, 15.65)
    sess.update(s, r, has_ev_meter=False, now=0)
    sess.update(s, r, has_ev_meter=False, now=1800)
    assert sess.charging_time_s == 1800
    assert sess.energy_kwh == pytest.approx(1.8)


def test_reset_on_disconnect():
    sess, s = Session(), EvseState(state="Charging", plug="Connected")
    r = PowerReading(3600, 3600, 0, 0, 15.65)
    sess.update(s, r, False, 0)
    sess.update(s, r, False, 100)
    s.plug, s.state = "Disconnected", "Ready to Charge"
    sess.update(s, PowerReading(0, 0, 0, 0, 0), False, 200)
    assert sess.charging_time_s == 0 and sess.energy_kwh == 0


def test_ev_meter_energy_comes_from_smartevse():
    sess = Session()
    s = EvseState(state="Charging", plug="Connected", ev_energy_wh=4520)
    sess.update(s, PowerReading(0, 0, 0, 0, 0), has_ev_meter=True, now=10)
    assert sess.energy_kwh == pytest.approx(4.52)


def test_ev_meter_energy_is_zero_when_disconnected_or_unknown():
    sess = Session()
    r = PowerReading(0, 0, 0, 0, 0)
    s = EvseState(state="Ready to Charge", plug="Disconnected",
                  ev_energy_wh=4520)
    sess.update(s, r, True, 0)
    assert sess.energy_kwh == 0
    s = EvseState(state="Charging", plug="Connected", ev_energy_wh=None)
    sess.update(s, r, True, 1)
    assert sess.energy_kwh == 0


def test_counts_again_from_zero_after_reconnect():
    sess = Session()
    r = PowerReading(3600, 3600, 0, 0, 15.65)
    s = EvseState(state="Charging", plug="Connected")
    sess.update(s, r, False, 0)
    sess.update(s, r, False, 100)
    s.plug, s.state = "Disconnected", "Ready to Charge"
    sess.update(s, r, False, 200)
    s.plug, s.state = "Connected", "Charging"
    sess.update(s, r, False, 300)
    sess.update(s, r, False, 400)
    assert sess.charging_time_s == 100
    assert sess.energy_kwh == pytest.approx(0.1)


def test_no_counting_when_not_charging():
    sess = Session()
    s = EvseState(state="Ready to Charge", plug="Connected")
    r = PowerReading(3600, 3600, 0, 0, 15.65)
    sess.update(s, r, False, 0)
    sess.update(s, r, False, 500)
    assert sess.charging_time_s == 0 and sess.energy_kwh == 0
