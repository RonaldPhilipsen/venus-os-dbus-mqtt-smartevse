import os

import pytest

from smartevse.config import load_config, serial_from_prefix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(ROOT, "config.sample.ini")


def test_loads_example_config():
    cfg = load_config(SAMPLE)
    assert cfg.device_instance == 43
    assert cfg.position == 1 and cfg.has_ev_meter is True
    assert cfg.topic_prefix == "SmartEVSE/51446"
    assert cfg.battery_enabled is True and cfg.battery_interval_s == 10
    assert cfg.grid_enabled is False and cfg.grid_interval_s == 2
    assert cfg.offline_timeout_s == 60 and cfg.nominal_voltage == 230


def test_missing_optional_keys_use_defaults(tmp_path):
    p = tmp_path / "c.ini"
    p.write_text("[MQTT]\nHost = h\nTopicPrefix = SmartEVSE/1/\n")
    cfg = load_config(str(p))
    assert cfg.mqtt_port == 1883 and cfg.device_instance == 43
    assert cfg.topic_prefix == "SmartEVSE/1"  # trailing slash removed
    assert cfg.grid_enabled is False


def test_missing_host_raises(tmp_path):
    p = tmp_path / "c.ini"
    p.write_text("[MQTT]\nTopicPrefix = x\n")
    with pytest.raises(ValueError):
        load_config(str(p))


def test_serial_from_prefix():
    assert serial_from_prefix("SmartEVSE/51446") == "51446"
    assert serial_from_prefix("garage") == "garage"


def test_percent_in_password_is_literal(tmp_path):
    p = tmp_path / "c.ini"
    p.write_text("[MQTT]\nHost = h\nTopicPrefix = x\nPassword = pa%ss\n")
    assert load_config(str(p)).mqtt_password == "pa%ss"


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("BATTERY", "IntervalSeconds", "0"),
        ("GRID", "IntervalSeconds", "-2"),
        ("MQTT", "OfflineTimeoutSeconds", "0"),
        ("BATTERY", "IntervalSeconds", "nan"),
        ("GRID", "IntervalSeconds", "inf"),
    ],
)
def test_interval_and_timeout_must_be_positive(tmp_path, section, key, value):
    p = tmp_path / "c.ini"
    text = "[MQTT]\nHost = h\nTopicPrefix = x\n"
    if section == "MQTT":
        text += "%s = %s\n" % (key, value)
    else:
        text += "[%s]\n%s = %s\n" % (section, key, value)
    p.write_text(text)
    with pytest.raises(ValueError):
        load_config(str(p))
