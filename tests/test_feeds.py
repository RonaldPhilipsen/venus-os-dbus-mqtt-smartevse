from typing import List

from smartevse.feeds import BusReader, Feed, GridEnergy
from smartevse.payloads import battery_payload, grid_payload


class BusError(Exception):
    """Stands in for dbus.exceptions.DBusException."""


class FakeBus:
    def __init__(self, values=None, names=()):
        self.values = dict(values or {})
        self.names: List[str] = list(names)
        self.calls = 0

    def get_value(self, service, path):
        self.calls += 1
        key = (service, path)
        if key not in self.values:
            raise BusError("org.freedesktop.DBus.Error.ServiceUnknown")
        return self.values[key]

    def list_names(self):
        return self.names


SYSTEM = "com.victronenergy.system"
BATTERY = (SYSTEM, "/Dc/Battery/Power")


def battery_feed(bus, out):
    reader = BusReader(bus.get_value, (BusError,))
    return Feed(lambda: battery_payload(reader.number(*BATTERY), 230), out.append)


def test_reader_reads_current_value_each_call():
    bus = FakeBus({BATTERY: 460.0})
    reader = BusReader(bus.get_value, (BusError,))
    assert reader.number(*BATTERY) == 460.0
    bus.values[BATTERY] = 920
    assert reader.number(*BATTERY) == 920.0 and bus.calls == 2


def test_reader_failure_or_invalid_gives_none():
    bus = FakeBus({(SYSTEM, "/Invalid"): []})
    reader = BusReader(bus.get_value, (BusError,))
    assert reader.number(*BATTERY) is None
    assert reader.number(SYSTEM, "/Invalid") is None


def test_battery_feed_stops_when_system_service_is_gone():
    bus = FakeBus({BATTERY: 460.0})
    out = []
    feed = battery_feed(bus, out)
    assert feed.tick() and out == ["20"]
    del bus.values[BATTERY]  # systemcalc stops or restarts
    assert feed.tick() and out == ["20"]
    bus.values[BATTERY] = -230.0  # new owner of the name
    assert feed.tick() and out == ["20", "-10"]


def test_feed_publishes_nothing_when_reader_returns_none_or_raises():
    out = []
    reader = BusReader(lambda s, p: None, (BusError,))
    Feed(lambda: battery_payload(reader.number(*BATTERY), 230), out.append).tick()

    def boom(service, path):
        raise RuntimeError("unexpected")

    reader = BusReader(boom, (BusError,))
    assert Feed(lambda: battery_payload(reader.number(*BATTERY), 230), out.append).tick() is True
    assert out == []


def test_grid_feed_stops_without_system_service():
    bus = FakeBus()
    reader = BusReader(bus.get_value, (BusError,))
    energy = GridEnergy(bus.list_names, reader)
    out = []
    Feed(
        lambda: grid_payload(
            *[reader.number(SYSTEM, "/Ac/Grid/L%d/Power" % n) for n in (1, 2, 3)],
            energy_kwh=energy.kwh(),
            nominal_voltage=230,
        ),
        out.append,
    ).tick()
    assert out == []


GRID_A = "com.victronenergy.grid.cgwacs_ttyUSB0"
GRID_B = "com.victronenergy.grid.http_40"
ENERGY = "/Ac/Energy/Forward"


def test_grid_energy_scans_and_reads():
    bus = FakeBus({(GRID_A, ENERGY): 12.5}, names=["com.victronenergy.system", GRID_A])
    energy = GridEnergy(bus.list_names, BusReader(bus.get_value, (BusError,)))
    assert energy.kwh() is None  # no scan yet
    assert energy.rescan() is True and energy.service == GRID_A
    assert energy.kwh() == 12.5
    bus.values[(GRID_A, ENERGY)] = 13.0
    assert energy.kwh() == 13.0


def test_grid_energy_rescans_when_call_fails():
    bus = FakeBus({(GRID_A, ENERGY): 12.5}, names=[GRID_A])
    energy = GridEnergy(bus.list_names, BusReader(bus.get_value, (BusError,)))
    energy.rescan()
    del bus.values[(GRID_A, ENERGY)]
    bus.names = [GRID_B]
    bus.values[(GRID_B, ENERGY)] = 7.0
    assert energy.kwh() is None and energy.service == GRID_B
    assert energy.kwh() == 7.0


def test_grid_energy_scan_failure_is_quiet():
    def list_names():
        raise BusError("no bus")

    energy = GridEnergy(list_names, BusReader(lambda s, p: 1.0, (BusError,)))
    assert energy.rescan() is True and energy.service is None
    assert energy.kwh() is None
