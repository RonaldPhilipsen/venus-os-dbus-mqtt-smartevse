"""Session counters for charging time and energy. No dbus or paho imports."""
from typing import Optional

from smartevse.mapping import PowerReading
from smartevse.state import EvseState


class Session:
    def __init__(self) -> None:
        self._last_time = None  # type: Optional[float]
        self._charging_s = 0.0
        self._estimated_wh = 0.0
        self._ev_energy_kwh = 0.0
        self._has_ev_meter = False

    def update(self, s: EvseState, reading: PowerReading,
               has_ev_meter: bool, now: float) -> None:
        # The first call only stores the time. A clock step back adds nothing.
        dt = 0.0 if self._last_time is None else max(0.0, now - self._last_time)
        self._last_time = now
        self._has_ev_meter = has_ev_meter

        if s.plug == "Disconnected":
            self._charging_s = 0.0
            self._estimated_wh = 0.0
            self._ev_energy_kwh = 0.0
            self._last_time = None  # the next session starts at the next call
            return

        if s.state == "Charging":
            self._charging_s += dt
            self._estimated_wh += reading.total_w * dt / 3600.0
        self._ev_energy_kwh = (s.ev_energy_wh or 0) / 1000.0

    def pause(self) -> None:
        """Forget the last time, so a data gap adds no time or energy."""
        self._last_time = None

    @property
    def charging_time_s(self) -> int:
        return int(self._charging_s)

    @property
    def energy_kwh(self) -> float:
        if self._has_ev_meter:
            return self._ev_energy_kwh
        return self._estimated_wh / 1000.0
