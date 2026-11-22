"""Periodic feeds from Victron D-Bus values to SmartEVSE MQTT topics.

No dbus imports. The entry script passes in the D-Bus calls and the
D-Bus exception type, so the tests run without dbus.
"""
import logging
from typing import Any, Callable, Iterable, Optional, Tuple, Type

log = logging.getLogger("smartevse.feeds")

GRID_PREFIX = "com.victronenergy.grid."
GRID_ENERGY_PATH = "/Ac/Energy/Forward"

# get_value(service, path) returns the unwrapped value of one D-Bus item.
GetValue = Callable[[str, str], Any]
Errors = Tuple[Type[BaseException], ...]


def number(value: Any) -> Optional[float]:
    """Return a D-Bus value as float, or None if it is missing or not a number.

    velib returns None or an empty list for an invalid value.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


class BusReader:
    """Reads one D-Bus value at each call.

    Each read goes to the service that owns the name at that moment, so a
    restarted service never leaves a stale cached value. A failed call
    gives None.
    """

    def __init__(self, get_value: GetValue, errors: Errors) -> None:
        self._get_value = get_value
        self._errors = errors

    def read(self, service: str, path: str) -> Any:
        """Return the value, or raise one of the errors on a failed call."""
        return self._get_value(service, path)

    def number(self, service: str, path: str) -> Optional[float]:
        try:
            return number(self._get_value(service, path))
        except self._errors:
            return None

    @property
    def errors(self) -> Errors:
        return self._errors


class GridEnergy:
    """Reads /Ac/Energy/Forward of the first com.victronenergy.grid.* service."""

    def __init__(self, list_names: Callable[[], Iterable[Any]],
                 reader: BusReader) -> None:
        self._list_names = list_names
        self._reader = reader
        self._service = None  # type: Optional[str]

    @property
    def service(self) -> Optional[str]:
        return self._service

    def rescan(self) -> bool:
        """Find a grid meter service if none is known. Returns True for GLib."""
        if self._service is None:
            try:
                names = sorted(str(n) for n in self._list_names()
                               if str(n).startswith(GRID_PREFIX))
            except self._reader.errors:
                return True
            if names:
                self._service = names[0]
                log.info("grid meter service: %s", self._service)
        return True

    def kwh(self) -> Optional[float]:
        if self._service is None:
            return None
        try:
            return number(self._reader.read(self._service, GRID_ENERGY_PATH))
        except self._reader.errors:
            log.info("grid meter %s did not reply, scanning again",
                     self._service)
            self._service = None
            self.rescan()
            return None


class Feed:
    def __init__(self, read: Callable[[], Optional[str]],
                 publish: Callable[[str], None]) -> None:
        self._read = read
        self._publish = publish

    def tick(self) -> bool:
        """Publish one value. Always returns True so the GLib timer stays."""
        try:
            payload = self._read()
            if payload is not None:
                self._publish(payload)
        except Exception:
            log.exception("feed update failed")
        return True
