"""Payload strings for the SmartEVSE /Set/HomeBatteryCurrent and /Set/MainsMeter topics.

Currents are in deciamps, energy in Wh, as the SmartEVSE expects.
No dbus or paho imports.
"""
import math
from typing import Optional

# SmartEVSE phase currents must lie strictly between these deciamp limits.
_PHASE_LIMIT_DA = 2000


def _finite(value: Optional[float]) -> Optional[float]:
    """Return the value, or None if it is missing, NaN or infinite."""
    if value is None or not math.isfinite(value):
        return None
    return value


def _deciamps(power_w: float, nominal_voltage: float) -> int:
    return round(power_w / nominal_voltage * 10)


def battery_payload(power_w: Optional[float], nominal_voltage: float) -> Optional[str]:
    """Return the battery current in deciamps, or None if the power is unknown."""
    power_w = _finite(power_w)
    if power_w is None:
        return None
    return str(_deciamps(power_w, nominal_voltage))


def grid_payload(l1_w: Optional[float], l2_w: Optional[float], l3_w: Optional[float],
                 energy_kwh: Optional[float], nominal_voltage: float) -> Optional[str]:
    """Return "L1:L2:L3:W:WH" for the mains meter, or None if the data is unusable.

    L1 must be known. A missing L2 or L3 counts as 0 A and 0 W. A missing
    energy value is sent as -1 Wh.
    """
    l1_w = _finite(l1_w)
    if l1_w is None:
        return None
    l2_w = _finite(l2_w)
    l3_w = _finite(l3_w)

    currents = []
    for power_w in (l1_w, l2_w or 0, l3_w or 0):
        da = _deciamps(power_w, nominal_voltage)
        if not -_PHASE_LIMIT_DA < da < _PHASE_LIMIT_DA:
            return None
        currents.append(da)

    watts = round(l1_w + (l2_w or 0) + (l3_w or 0))
    energy = _finite(energy_kwh)
    wh = -1 if energy is None else round(energy * 1000)
    return "%d:%d:%d:%d:%d" % (currents[0], currents[1], currents[2], watts, wh)
