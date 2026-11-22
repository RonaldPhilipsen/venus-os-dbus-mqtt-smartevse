#!/usr/bin/env python3
"""Venus OS driver: SmartEVSE over MQTT as a Victron EV charger on D-Bus."""
import configparser
import logging
import os
import platform
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
# Bundled paho-mqtt goes first, velib_python comes from the GX device.
sys.path.insert(0, os.path.join(HERE, "ext"))
sys.path.insert(1, "/opt/victronenergy/dbus-systemcalc-py/ext/velib_python")

import dbus  # noqa: E402
from dbus.mainloop.glib import DBusGMainLoop  # noqa: E402
from gi.repository import GLib  # noqa: E402
from settingsdevice import SettingsDevice  # noqa: E402
from ve_utils import unwrap_dbus_value  # noqa: E402
from vedbus import VeDbusService  # noqa: E402

from smartevse import __version__  # noqa: E402
from smartevse.config import load_config, serial_from_prefix  # noqa: E402
from smartevse.controller import Controller  # noqa: E402
from smartevse.dbus_service import (PATHS, WRITEABLE_PATHS,  # noqa: E402
                                    publish_state)
from smartevse.feeds import BusReader, Feed, GridEnergy  # noqa: E402
from smartevse.mapping import MODE_AUTO, MODE_MANUAL, power_reading  # noqa: E402
from smartevse.mqtt_client import SmartEvseMqtt  # noqa: E402
from smartevse.payloads import battery_payload, grid_payload  # noqa: E402
from smartevse.session import Session  # noqa: E402
from smartevse.state import EvseState, apply_message, is_available  # noqa: E402

SYSTEM = "com.victronenergy.system"
BUS_ITEM = "com.victronenergy.BusItem"
DBUS_TIMEOUT_S = 1.0
GRID_RESCAN_S = 60
FATAL_DELAY_S = 60

log = logging.getLogger("smartevse")


def fatal(message, *args, exc_info=False):
    """Log an error and exit late, so daemontools does not restart in a tight loop."""
    log.error(message, *args, exc_info=exc_info)
    time.sleep(FATAL_DELAY_S)
    sys.exit(1)


def system_bus():
    if "DBUS_SESSION_BUS_ADDRESS" in os.environ:
        return dbus.SessionBus()
    return dbus.SystemBus()


def make_service(name):
    """Create a VeDbusService for both newer (register=False) and older vedbus."""
    try:
        return VeDbusService(name, register=False)
    except TypeError:
        return VeDbusService(name)


def bus_reader(bus):
    """Read D-Bus items with one call each, sent to the current owner.

    A VeDbusItemImport binds to the owner at creation time. After a restart
    of the service it keeps a stale value, so the feeds do not use it.
    """
    def get_value(service, path):
        return unwrap_dbus_value(bus.call_blocking(
            service, path, BUS_ITEM, "GetValue", "", [],
            timeout=DBUS_TIMEOUT_S))
    return BusReader(get_value, (dbus.exceptions.DBusException,))


def main():
    logging.basicConfig(stream=sys.stdout, level=logging.WARNING,
                        format="%(levelname)s %(name)s %(message)s")
    try:
        start()
    except Exception as e:
        fatal("startup failed: %s", e, exc_info=True)
    GLib.MainLoop().run()


def start():
    """Set up the D-Bus service, MQTT, and the timers. The caller runs the loop."""
    config_path = os.path.join(HERE, "config.ini")
    if not os.path.exists(config_path):
        fatal("config file not found: %s", config_path)
    try:
        cfg = load_config(config_path)
    except (ValueError, KeyError, configparser.Error) as e:
        fatal("invalid config file %s: %s", config_path, e)
    if cfg.nominal_voltage <= 0:
        fatal("NominalVoltage must be greater than 0, not %s",
              cfg.nominal_voltage)

    DBusGMainLoop(set_as_default=True)
    bus = system_bus()

    # 1. D-Bus service with all paths, then register.
    svc = make_service("com.victronenergy.evcharger.smartevse_%d"
                       % cfg.device_instance)
    svc.add_path("/Mgmt/ProcessName", __file__)
    svc.add_path("/Mgmt/ProcessVersion",
                 "%s on Python %s" % (__version__, platform.python_version()))
    svc.add_path("/Mgmt/Connection",
                 "MQTT %s:%d" % (cfg.mqtt_host, cfg.mqtt_port))
    svc.add_path("/DeviceInstance", cfg.device_instance)
    svc.add_path("/ProductId", 0xFFFF)
    svc.add_path("/ProductName", "SmartEVSE")
    svc.add_path("/CustomName", cfg.custom_name)
    svc.add_path("/FirmwareVersion", None)
    svc.add_path("/Serial", serial_from_prefix(cfg.topic_prefix))
    svc.add_path("/Position", cfg.position)
    svc.add_path("/Connected", 0)
    svc.add_path("/UpdateIndex", 0)

    state = EvseState()
    session = Session()
    holder = {}  # the controller and MQTT client, created below

    def on_write(path, value):
        now = time.time()
        ctrl = holder["controller"]
        try:
            if path == "/Mode":
                return ctrl.on_mode_write(int(value), state, now)
            if path == "/StartStop":
                return ctrl.on_start_stop_write(int(value), state, now)
            if path == "/SetCurrent":
                return ctrl.on_set_current_write(float(value), state, now)
        except (TypeError, ValueError, OverflowError):
            pass
        return False

    for path, fmt in PATHS.items():
        writeable = path in WRITEABLE_PATHS
        svc.add_path(path, None, gettextcallback=fmt, writeable=writeable,
                     onchangecallback=on_write if writeable else None)

    if hasattr(svc, "register"):
        svc.register()

    # 2. Stored Victron mode in localsettings. Default 1 (Auto).
    settings = SettingsDevice(
        bus,
        {"mode": ["/Settings/Devices/smartevse_%d/Mode" % cfg.device_instance,
                  MODE_AUTO, 0, 2]},
        lambda setting, old, new: None)
    initial_mode = int(settings["mode"])
    if initial_mode not in (MODE_MANUAL, MODE_AUTO):
        initial_mode = MODE_AUTO

    def store_mode(mode):
        settings["mode"] = mode

    # 3. MQTT. Callbacks arrive in the GLib thread through idle_add.
    def on_message(suffix, payload):
        now = time.time()
        apply_message(state, suffix, payload, now)
        if suffix == "/Mode":
            holder["controller"].on_mode_report(payload, now)
        return False

    def on_link(up):
        return False

    mqtt = SmartEvseMqtt(cfg, on_message, on_link, schedule=GLib.idle_add)
    controller = Controller(mqtt.publish_set, store_mode, initial_mode,
                            cfg.offline_timeout_s, log)
    holder["controller"] = controller

    # 4. Values from com.victronenergy.system and the grid meter. Each feed
    #    tick reads the values again, so nothing here needs systemcalc.
    reader = bus_reader(bus)

    # 5. Update D-Bus every second.
    def update():
        try:
            now = time.time()
            controller.check_pending(now)
            available = is_available(state, now, cfg.offline_timeout_s)
            reading = power_reading(state, cfg.has_ev_meter,
                                    cfg.nominal_voltage)
            if available:
                session.update(state, reading, cfg.has_ev_meter, now)
            else:
                session.pause()
            publish_state(svc, state, reading, session, controller, available)
        except Exception:
            log.exception("update failed")
        return True

    GLib.timeout_add(1000, update)

    # 6. Feeds to SmartEVSE.
    if cfg.battery_enabled:
        battery = Feed(
            lambda: battery_payload(
                reader.number(SYSTEM, "/Dc/Battery/Power"),
                cfg.nominal_voltage),
            lambda p: mqtt.publish_set("HomeBatteryCurrent", p))
        GLib.timeout_add(max(1, int(cfg.battery_interval_s * 1000)),
                         battery.tick)

    if cfg.grid_enabled:
        energy = GridEnergy(bus.list_names, reader)
        energy.rescan()
        GLib.timeout_add_seconds(GRID_RESCAN_S, energy.rescan)
        grid = Feed(
            lambda: grid_payload(
                *[reader.number(SYSTEM, "/Ac/Grid/L%d/Power" % n)
                  for n in (1, 2, 3)],
                energy_kwh=energy.kwh(),
                nominal_voltage=cfg.nominal_voltage),
            lambda p: mqtt.publish_set("MainsMeter", p))
        GLib.timeout_add(max(1, int(cfg.grid_interval_s * 1000)), grid.tick)

    # 7. Sign of life, then start MQTT.
    def sign_of_life():
        log.warning("sign of life: connected=%s power=%s status=%s",
                    svc["/Connected"], svc["/Ac/Power"], svc["/Status"])
        return True

    if cfg.sign_of_life_minutes > 0:
        GLib.timeout_add_seconds(cfg.sign_of_life_minutes * 60, sign_of_life)

    mqtt.start()


if __name__ == "__main__":
    main()
