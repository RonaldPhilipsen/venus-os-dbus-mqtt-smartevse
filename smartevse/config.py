"""Configuration loader for dbus-smartevse."""

import configparser
import math
from dataclasses import dataclass


@dataclass
class Config:
    device_instance: int
    custom_name: str
    sign_of_life_minutes: int
    nominal_voltage: float
    position: int
    has_ev_meter: bool
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str
    mqtt_password: str
    topic_prefix: str
    offline_timeout_s: float
    battery_enabled: bool
    battery_interval_s: float
    grid_enabled: bool
    grid_interval_s: float


def load_config(path: str) -> Config:
    parser = configparser.ConfigParser(interpolation=None)
    if not parser.read(path):
        raise ValueError("cannot read config file: %s" % path)

    d = parser["DEFAULT"]
    mqtt = parser["MQTT"] if parser.has_section("MQTT") else {}
    battery = parser["BATTERY"] if parser.has_section("BATTERY") else {}
    grid = parser["GRID"] if parser.has_section("GRID") else {}

    host = mqtt.get("Host", "").strip() if mqtt else ""
    prefix = mqtt.get("TopicPrefix", "").strip().rstrip("/") if mqtt else ""
    if not host:
        raise ValueError("[MQTT] Host is required")
    if not prefix:
        raise ValueError("[MQTT] TopicPrefix is required")

    def flag(section, key, default):
        return str(section.get(key, default)).strip().lower() in ("1", "true", "yes", "on")

    cfg = Config(
        device_instance=int(d.get("DeviceInstance", "43")),
        custom_name=d.get("CustomName", "SmartEVSE"),
        sign_of_life_minutes=int(d.get("SignOfLifeLog", "10")),
        nominal_voltage=float(d.get("NominalVoltage", "230")),
        position=int(d.get("Position", "1")),
        has_ev_meter=flag(d, "HasEVMeter", "1"),
        mqtt_host=host,
        mqtt_port=int(mqtt.get("Port", "1883")),
        mqtt_username=mqtt.get("Username", ""),
        mqtt_password=mqtt.get("Password", ""),
        topic_prefix=prefix,
        offline_timeout_s=float(mqtt.get("OfflineTimeoutSeconds", "60")),
        battery_enabled=flag(battery, "Enabled", "1"),
        battery_interval_s=float(battery.get("IntervalSeconds", "10")),
        grid_enabled=flag(grid, "Enabled", "0"),
        grid_interval_s=float(grid.get("IntervalSeconds", "2")),
    )
    for name, value in (
        ("[MQTT] OfflineTimeoutSeconds", cfg.offline_timeout_s),
        ("[BATTERY] IntervalSeconds", cfg.battery_interval_s),
        ("[GRID] IntervalSeconds", cfg.grid_interval_s),
    ):
        if not (math.isfinite(value) and value > 0):
            raise ValueError("%s must be greater than 0, not %s" % (name, value))
    return cfg


def serial_from_prefix(prefix: str) -> str:
    """Return the last topic segment, used as the device serial."""
    return prefix.rstrip("/").rsplit("/", 1)[-1]
