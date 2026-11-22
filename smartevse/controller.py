"""Handles writes from the GX screen and VRM. No dbus or paho imports."""
import logging
import math
from typing import Callable, Optional, Tuple

from smartevse.mapping import MODE_AUTO, MODE_MANUAL
from smartevse.state import EvseState, is_available

CONFIRM_TIMEOUT_S = 10.0
_EVSE_MODE = {MODE_MANUAL: "Smart", MODE_AUTO: "Solar"}
_REPORT_TO_MODE = {"Smart": MODE_MANUAL, "Normal": MODE_MANUAL,
                   "Solar": MODE_AUTO}


class Controller:
    def __init__(self, publish: Callable[[str, str], None],
                 store_mode: Callable[[int], None], initial_mode: int,
                 timeout_s: float, log: logging.Logger) -> None:
        self._publish = publish
        self._store_mode = store_mode
        self._mode = initial_mode
        self._timeout_s = timeout_s
        self._log = log
        self._pending = None  # type: Optional[Tuple[str, float]]
        self._last_report = None  # type: Optional[str]

    @property
    def mode(self) -> int:
        return self._mode

    def _set_mode(self, mode: int) -> None:
        self._mode = mode
        self._store_mode(mode)

    def _send_mode(self, evse_mode: str, now: float) -> None:
        self._publish("Mode", evse_mode)
        self._pending = (evse_mode, now)

    def on_mode_write(self, value: int, s: EvseState, now: float) -> bool:
        if not is_available(s, now, self._timeout_s):
            return False
        if value not in _EVSE_MODE:  # includes 2 (Scheduled)
            return False
        self._set_mode(value)
        if s.mode not in ("Off", "Pause"):
            self._send_mode(_EVSE_MODE[value], now)
        return True

    def on_start_stop_write(self, value: int, s: EvseState,
                            now: float) -> bool:
        if not is_available(s, now, self._timeout_s):
            return False
        if value == 1:
            self._send_mode(_EVSE_MODE[self._mode], now)
        elif value == 0:
            self._send_mode("Pause", now)
        else:
            return False
        return True

    def on_set_current_write(self, value: float, s: EvseState,
                             now: float) -> bool:
        if not is_available(s, now, self._timeout_s):
            return False
        if self._mode == MODE_AUTO or not math.isfinite(value) or value < 0:
            return False
        if s.max_current_da is not None and value > s.max_current_da / 10:
            return False
        self._publish("CurrentOverride", str(round(value * 10)))
        return True

    def on_mode_report(self, evse_mode: str, now: float) -> None:
        self.check_pending(now)
        self._last_report = evse_mode
        if self._pending is not None:
            if evse_mode != self._pending[0]:
                return
            self._pending = None
        self._follow(evse_mode)

    def _follow(self, evse_mode: Optional[str]) -> None:
        mode = _REPORT_TO_MODE.get(evse_mode)
        if mode is not None and mode != self._mode:
            self._set_mode(mode)

    def check_pending(self, now: float) -> None:
        if self._pending is None:
            return
        expected, sent_at = self._pending
        if now - sent_at < CONFIRM_TIMEOUT_S:
            return
        self._pending = None
        self._log.warning("SmartEVSE did not switch to %s within %d s",
                          expected, CONFIRM_TIMEOUT_S)
        self._follow(self._last_report)
