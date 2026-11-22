import logging

from smartevse.controller import Controller
from smartevse.dbus_service import PATHS, WRITEABLE_PATHS, publish_state
from smartevse.feeds import Feed, number
from smartevse.mapping import PowerReading
from smartevse.session import Session
from smartevse.state import EvseState

ctrl = Controller(lambda n, p: None, lambda m: None, 1, 60, logging.getLogger("t"))


def test_publish_state_when_available():
    svc = {"/UpdateIndex": 255}
    s = EvseState(
        online=True,
        mode="Smart",
        state="Charging",
        plug="Connected",
        error="None",
        charge_current_da=160,
        override_da=0,
        max_current_da=320,
    )
    publish_state(svc, s, PowerReading(3680, 3680, 0, 0, 16.0), Session(), ctrl, True)
    assert svc["/Connected"] == 1 and svc["/Status"] == 2 and svc["/Mode"] == 0
    assert svc["/Ac/Power"] == 3680 and svc["/MaxCurrent"] == 32 and svc["/SetCurrent"] == 16
    assert svc["/UpdateIndex"] == 0


def test_publish_state_when_unavailable():
    svc = {"/UpdateIndex": 0}
    publish_state(svc, EvseState(), PowerReading(0, 0, 0, 0, 0), Session(), ctrl, False)
    assert svc["/Connected"] == 0 and svc["/Ac/Power"] is None and svc["/Status"] is None


def test_feed_skips_none():
    out = []
    assert Feed(lambda: None, out.append).tick() is True and out == []
    Feed(lambda: "100", out.append).tick()
    assert out == ["100"]


# Extra checks beyond the brief.


def test_unavailable_clears_every_reading_path():
    svc = {"/UpdateIndex": 7}
    publish_state(svc, EvseState(), PowerReading(0, 0, 0, 0, 0), Session(), ctrl, False)
    assert all(svc[p] is None for p in PATHS)
    assert svc["/UpdateIndex"] == 8


def test_available_writes_every_reading_path():
    svc = {"/UpdateIndex": 0}
    s = EvseState(
        online=True,
        mode="Solar",
        state="Charging",
        plug="Connected",
        error="None",
        charge_current_da=60,
        override_da=0,
        max_current_da=160,
        temp_c=41,
    )
    publish_state(svc, s, PowerReading(1380, 1380, 0, 0, 6.0), Session(), ctrl, True)
    assert set(PATHS) <= set(svc)
    assert svc["/MCU/Temperature"] == 41 and svc["/Current"] == 6.0
    assert svc["/Ac/L1/Power"] == 1380 and svc["/Ac/L2/Power"] == 0
    assert svc["/Mode"] == 1 and svc["/StartStop"] == 1


def test_start_stop_keeps_previous_value_for_unknown_mode():
    svc = {"/UpdateIndex": 0, "/StartStop": 1}
    s = EvseState(online=True, mode=None)
    publish_state(svc, s, PowerReading(0, 0, 0, 0, 0), Session(), ctrl, True)
    assert svc["/StartStop"] == 1
    svc = {"/UpdateIndex": 0, "/StartStop": None}
    publish_state(svc, s, PowerReading(0, 0, 0, 0, 0), Session(), ctrl, True)
    assert svc["/StartStop"] == 0


def test_paused_shows_start_stop_zero_and_keeps_mode():
    svc = {"/UpdateIndex": 0, "/StartStop": 1}
    s = EvseState(online=True, mode="Pause", plug="Connected", state="Connected to EV")
    publish_state(svc, s, PowerReading(0, 0, 0, 0, 0), Session(), ctrl, True)
    assert svc["/StartStop"] == 0 and svc["/Mode"] == ctrl.mode


def test_paths_and_formatters():
    assert set(WRITEABLE_PATHS) == {"/Mode", "/StartStop", "/SetCurrent"}
    assert set(WRITEABLE_PATHS) <= set(PATHS)
    assert "/Ac/Voltage" not in PATHS
    assert PATHS["/Ac/Power"]("/Ac/Power", 3680) == "3680W"
    assert PATHS["/Current"]("/Current", 16.04) == "16.0A"
    assert PATHS["/Ac/Energy/Forward"]("/Ac/Energy/Forward", 1.234) == "1.23kWh"
    assert PATHS["/ChargingTime"]("/ChargingTime", 60) == "60s"
    assert PATHS["/MCU/Temperature"]("/MCU/Temperature", 41) == "41°C"
    for path, fmt in PATHS.items():
        assert isinstance(fmt(path, None), str)


def test_feed_survives_read_error():
    out = []

    def broken():
        raise RuntimeError("dbus gone")

    assert Feed(broken, out.append).tick() is True and out == []


def test_number():
    assert number(5) == 5.0 and number(2.5) == 2.5
    assert number(None) is None and number([]) is None and number("x") is None
    assert number(True) is None
