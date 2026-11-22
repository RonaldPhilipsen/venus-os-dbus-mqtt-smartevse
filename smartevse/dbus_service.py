"""Victron D-Bus paths and the function that fills them.

publish_state writes to any mapping with [] access (a VeDbusService or a
dict), so this module does not import dbus or vedbus.
"""
from typing import Any, Callable, Dict, MutableMapping, Optional

from smartevse.controller import Controller
from smartevse.mapping import (PowerReading, victron_mode, victron_set_current,
                               victron_start_stop, victron_status)
from smartevse.session import Session
from smartevse.state import EvseState


def _unit(fmt: str) -> Callable[[str, Any], str]:
    def text(path: str, value: Any) -> str:
        if value is None:
            return "---"
        return fmt.format(value)
    return text


_w = _unit("{:.0f}W")
_a = _unit("{:.1f}A")
_kwh = _unit("{:.2f}kWh")
_s = _unit("{}s")
_deg_c = _unit("{}°C")
_plain = _unit("{}")

# Reading path -> text formatter (gettextcallback for VeDbusService).
PATHS = {
    "/Ac/Power": _w,
    "/Ac/L1/Power": _w,
    "/Ac/L2/Power": _w,
    "/Ac/L3/Power": _w,
    "/Current": _a,
    "/Ac/Energy/Forward": _kwh,
    "/ChargingTime": _s,
    "/MaxCurrent": _a,
    "/Status": _plain,
    "/Mode": _plain,
    "/StartStop": _plain,
    "/SetCurrent": _a,
    "/MCU/Temperature": _deg_c,
}  # type: Dict[str, Callable[[str, Any], str]]

# Paths that the GX screen and VRM can write.
WRITEABLE_PATHS = ("/Mode", "/StartStop", "/SetCurrent")


def _read(svc: MutableMapping[str, Any], path: str) -> Any:
    try:
        return svc[path]
    except KeyError:
        return None


def _amps(deciamps: Optional[int]) -> Optional[float]:
    return None if deciamps is None else deciamps / 10


def publish_state(svc: MutableMapping[str, Any], s: EvseState,
                  reading: PowerReading, sess: Session,
                  controller: Controller, available: bool) -> None:
    if available:
        last_start_stop = _read(svc, "/StartStop")
        values = {
            "/Ac/Power": reading.total_w,
            "/Ac/L1/Power": reading.l1_w,
            "/Ac/L2/Power": reading.l2_w,
            "/Ac/L3/Power": reading.l3_w,
            "/Current": reading.current_a,
            "/Ac/Energy/Forward": sess.energy_kwh,
            "/ChargingTime": sess.charging_time_s,
            "/MaxCurrent": _amps(s.max_current_da),
            "/Status": victron_status(s),
            "/Mode": victron_mode(s.mode, controller.mode),
            "/StartStop": victron_start_stop(
                s.mode, 0 if last_start_stop is None else last_start_stop),
            "/SetCurrent": victron_set_current(s),
            "/MCU/Temperature": s.temp_c,
        }
    else:
        values = dict.fromkeys(PATHS)
    for path in PATHS:
        svc[path] = values[path]
    svc["/Connected"] = 1 if available else 0
    index = _read(svc, "/UpdateIndex")
    svc["/UpdateIndex"] = 0 if index is None else (index + 1) % 256
