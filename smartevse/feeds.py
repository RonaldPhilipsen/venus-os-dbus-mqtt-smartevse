"""Periodic feeds from Victron D-Bus values to SmartEVSE MQTT topics."""
import logging
from typing import Any, Callable, Optional

log = logging.getLogger("smartevse.feeds")


def number(value: Any) -> Optional[float]:
    """Return a D-Bus value as float, or None if it is missing or not a number.

    velib returns None or an empty list for an invalid value.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


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
