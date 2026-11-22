from smartevse.state import EvseState, apply_message, is_available


def test_numeric_and_text_topics():
    s = EvseState()
    apply_message(s, "/EVChargePower", "7360", now=5.0)
    apply_message(s, "/EVCurrentL2", "106", now=5.0)
    apply_message(s, "/State", "Charging", now=5.0)
    assert s.ev_power_w == 7360 and s.ev_current_da[1] == 106
    assert s.state == "Charging" and s.last_message == 5.0


def test_bad_numeric_payload_keeps_last_value():
    s = EvseState()
    apply_message(s, "/EVChargePower", "1000", now=1.0)
    apply_message(s, "/EVChargePower", "", now=2.0)
    apply_message(s, "/EVChargePower", "N/A", now=3.0)
    assert s.ev_power_w == 1000


def test_offline_and_stale():
    s = EvseState()
    apply_message(s, "/connected", "online", now=100.0)
    assert is_available(s, now=150.0, timeout_s=60)
    assert not is_available(s, now=161.0, timeout_s=60)
    apply_message(s, "/connected", "offline", now=170.0)
    assert not is_available(s, now=170.0, timeout_s=60)


def test_unknown_topic_only_updates_time():
    s = EvseState()
    apply_message(s, "/LEDColorOff", "0,0,0", now=9.0)
    assert s.last_message == 9.0 and s.mode is None
