"""SmartEVSE state, built from MQTT messages. No dbus or paho imports."""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class EvseState:
    online: Optional[bool] = None
    mode: Optional[str] = None
    state: Optional[str] = None
    error: Optional[str] = None
    plug: Optional[str] = None
    charge_current_da: Optional[int] = None
    override_da: Optional[int] = None
    max_current_da: Optional[int] = None
    phases: Optional[int] = None
    ev_current_da: List[Optional[int]] = field(
        default_factory=lambda: [None, None, None])
    ev_power_w: Optional[int] = None
    ev_energy_wh: Optional[int] = None
    temp_c: Optional[int] = None
    last_message: float = 0.0


def _text(payload):
    return payload


def _online(payload):
    return payload.strip() == "online"


def _int(payload):
    # int(float()) accepts "7360" and "7360.0"; raises ValueError otherwise.
    return int(float(payload.strip()))


# suffix -> (field name, parser, index for list fields or None)
_TOPICS = {
    "/connected": ("online", _online, None),
    "/Mode": ("mode", _text, None),
    "/State": ("state", _text, None),
    "/Error": ("error", _text, None),
    "/EVPlugState": ("plug", _text, None),
    "/ChargeCurrent": ("charge_current_da", _int, None),
    "/ChargeCurrentOverride": ("override_da", _int, None),
    "/MaxCurrent": ("max_current_da", _int, None),
    "/NrOfPhases": ("phases", _int, None),
    "/EVCurrentL1": ("ev_current_da", _int, 0),
    "/EVCurrentL2": ("ev_current_da", _int, 1),
    "/EVCurrentL3": ("ev_current_da", _int, 2),
    "/EVChargePower": ("ev_power_w", _int, None),
    "/EVEnergyCharged": ("ev_energy_wh", _int, None),
    "/ESPTemp": ("temp_c", _int, None),
}


def apply_message(state: EvseState, suffix: str, payload: str,
                  now: float) -> None:
    """Update state from one message. Bad numbers keep the last value."""
    state.last_message = now
    entry = _TOPICS.get(suffix)
    if entry is None:
        return
    name, parser, index = entry
    try:
        value = parser(payload)
    except (ValueError, OverflowError):
        return
    if index is None:
        setattr(state, name, value)
    else:
        getattr(state, name)[index] = value


def is_available(state: EvseState, now: float, timeout_s: float) -> bool:
    return state.online is not False and now - state.last_message <= timeout_s
