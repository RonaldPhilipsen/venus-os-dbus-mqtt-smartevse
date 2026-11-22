"""Mapping from SmartEVSE state to Victron values. No dbus or paho imports."""

from typing import NamedTuple, Optional

from smartevse.state import EvseState

MODE_MANUAL = 0
MODE_AUTO = 1
MODE_SCHEDULED = 2

STATUS_DISCONNECTED = 0
STATUS_CONNECTED = 1
STATUS_CHARGING = 2
STATUS_WAIT_SUN = 4
STATUS_WAIT_START = 6
STATUS_ERROR = 8


def victron_mode(evse_mode: Optional[str], last_mode: int) -> int:
    if evse_mode in ("Smart", "Normal"):
        return MODE_MANUAL
    if evse_mode == "Solar":
        return MODE_AUTO
    return last_mode


def victron_start_stop(evse_mode: Optional[str], last: int) -> int:
    if evse_mode in ("Off", "Pause"):
        return 0
    if evse_mode in ("Normal", "Smart", "Solar"):
        return 1
    return last


def victron_status(s: EvseState) -> int:
    if s.error not in (None, "None"):
        return STATUS_ERROR  # Temperature High may become 14 later
    if s.state == "Ready to Charge" and s.plug == "Disconnected":
        return STATUS_DISCONNECTED
    if s.state == "Charging":
        return STATUS_CHARGING
    if s.mode == "Solar":
        return STATUS_WAIT_SUN
    if s.mode in ("Off", "Pause"):
        return STATUS_WAIT_START
    return STATUS_CONNECTED


def victron_set_current(s: EvseState) -> Optional[float]:
    if s.override_da:
        return s.override_da / 10
    if s.charge_current_da is not None:
        return s.charge_current_da / 10
    return None


class PowerReading(NamedTuple):
    total_w: float
    l1_w: float
    l2_w: float
    l3_w: float
    current_a: float


def power_reading(s: EvseState, has_ev_meter: bool, nominal_voltage: float) -> PowerReading:
    if has_ev_meter:
        return _metered(s)
    return _estimated(s, nominal_voltage)


def _metered(s: EvseState) -> PowerReading:
    total = s.ev_power_w or 0
    currents = [c or 0 for c in s.ev_current_da]
    current_sum = sum(currents)
    if current_sum > 0:
        l1, l2, l3 = [total * c / current_sum for c in currents]
    elif total > 0:
        l1, l2, l3 = total, 0, 0
    else:
        l1 = l2 = l3 = 0
    return PowerReading(total, l1, l2, l3, max(currents) / 10)


def _estimated(s: EvseState, nominal_voltage: float) -> PowerReading:
    if s.state != "Charging" or not s.charge_current_da:
        return PowerReading(0, 0, 0, 0, 0)
    amps = s.charge_current_da / 10
    phases = 3 if s.phases == 3 else 1
    per_phase = amps * nominal_voltage
    total = per_phase * phases
    if phases == 3:
        return PowerReading(total, per_phase, per_phase, per_phase, amps)
    return PowerReading(total, per_phase, 0, 0, amps)
